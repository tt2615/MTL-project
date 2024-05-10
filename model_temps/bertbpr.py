import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from transformers import BertModel, BertTokenizer
from evaluator import ACCURACY, CLASSIFICATION

# import numpy as np
import pandas as pd

class Attention(nn.Module):
    def __init__(self, input_dim):
        super(Attention, self).__init__()
        self.input_dim = input_dim
        self.query = nn.Linear(input_dim, input_dim)
        self.key = nn.Linear(input_dim, input_dim)
        self.value = nn.Linear(input_dim, input_dim)
        self.softmax = nn.Softmax(dim=2)
        
    def forward(self, x, q):
        queries = self.query(q) #batch*1*dim
        keys = self.key(x) #batch*feature*dim
        values = self.value(x) #batch*feature*dim
        scores = torch.bmm(queries, keys.transpose(1, 2)) / (self.input_dim ** 0.5) #batch*1*feature
        attention = self.softmax(scores) #batch*1*feature
        weighted = torch.bmm(attention, values) #batch*1*dim
        return weighted, attention.squeeze(1)
    

class BertAttBpr(nn.Module):
    def __init__(self, dim, p_cat_unique_count, u_cat_unique_count, embed_cols_count, num_cols_count, topic_num, user_cols_count, device, bert='bert-base-chinese'):
        super(BertAttBpr, self).__init__()
        # define parameters
        self.dim = dim
        self.embed_cols_count = embed_cols_count
        self.num_cols_count = num_cols_count
        self.topic_num = topic_num
        self.user_cols_count = user_cols_count
        self.device = device

        ## text input module
        # configuration = BertConfig.from_pretrained('bert-base-chinese', output_hidden_states=True, output_attentions=True)
        # configuration.hidden_dropout_prob = 0.8
        # configuration.attention_probs_dropout_prob = 0.8
        # self.title_bert = BertForSequenceClassification.from_pretrained('bert-base-chinese', config=configuration)
        self.tokenizer = BertTokenizer.from_pretrained(bert)
        self.title_bert = BertModel.from_pretrained(bert, output_attentions=True)
        self.bert_linear = nn.Sequential(
            nn.Linear(768, dim*2, bias=True),
            nn.ReLU(),
            nn.Linear(dim*2, dim, bias=True),
            nn.Dropout(0.1) 
        )

        ## cat input embedding module #'item_author', 'article_author', 'article_source'
        self.embedding_layer = nn.ModuleList()
        for i in range(embed_cols_count):
            self.embedding_layer.append(nn.Embedding(p_cat_unique_count[i], dim))

        ## num input network module #'item_views', 'item_comment_counts', 'article_likes'
        self.network_layer = nn.ModuleList()
        for i in range(num_cols_count):
            self.network_layer.append(nn.Sequential(
            nn.Linear(1, dim//2, bias=True),
            nn.ReLU(),
            nn.Linear(dim//2, dim, bias=True),
            nn.Dropout(0.1) 
        ))

        self.topic_layer = nn.Sequential(
            nn.Linear(topic_num, dim//2, bias=True),
            nn.ReLU(),
            nn.Linear(dim//2, dim, bias=True),
            nn.Dropout(0.1) 
        )

        self.user_attention_module = Attention(dim)
        self.post_attention_module = Attention(dim)
        self.task_embedding = nn.Parameter(torch.rand(1,1,dim), requires_grad=True)

        ## user input embedding module # 'item_author', 'article_author', 'article_source'
        self.user_embedding_layer = nn.ModuleList()
        for i in range(user_cols_count):
            self.user_embedding_layer.append(nn.Embedding(u_cat_unique_count[i], dim))

        # define evaluator
        self.evaluators = [ACCURACY(), CLASSIFICATION()]

    def forward(self, pos_input, neg_input):
        pos_score, p_feature_att_score, p_title_att_score = self.compute_score(pos_input)
        neg_score, n_feature_att_score, n_title_att_score = self.compute_score(neg_input)

        return pos_score, p_feature_att_score, p_title_att_score, neg_score, n_feature_att_score, n_title_att_score


    def compute_score(self, input):

        text_input, non_text_input, user_input = input

        ## news representation

        #text representation
        title_output = self.title_bert(text_input[:,0,:], attention_mask=text_input[:,1,:]) #batch*768
        text_rep = title_output.pooler_output #batch*768
        # text_rep = torch.flatten(text_rep, start_dim=1) #batch*(len*768)
        text_rep = self.bert_linear(text_rep).unsqueeze(1) #batch*1*dim
        # print(text_rep.shape)

        #extract attention: title_output.attentions has 12 (layers) of (batch*head(12)*len*len)
        title_att_score = torch.sum(title_output.attentions[-1],dim=1) #batch*len*len
        title_att_score = torch.sum(title_att_score,dim=1) #batch*len
        # print(title_att_score.shape)

        """
        Non-text-input:
            stock_code_index                         52
            sentiment_score                    0.200904
            month_index                               5
            year_index                                4
            eastmoney_robo_journalism_index           1
            media_robo_journalism_index               1
            SMA_robo_journalism_index                 1
            topics_val1                        0.012618
            topics_val2                        0.012623
            topics_val3                        0.012636
            topics_val4                        0.214114
            topics_val5                        0.225046
            topics_val6                        0.012619
            topics_val7                        0.122692
            topics_val8                        0.387651    
        """

        # #num representation
        if self.num_cols_count>0:
            num_reps = torch.zeros((non_text_input.shape[0],1,self.dim)).to(self.device)
            for i in range(self.num_cols_count):
                # self.network_layer[i].to(self.device)
                num_rep = self.network_layer[i](non_text_input[:,i].unsqueeze(1)) #batch*dim  
                num_reps = torch.cat((num_reps, num_rep.unsqueeze(1)),dim=1)
            num_reps = num_reps[:,1:,:] #batch*1*dim
        else:
            num_reps = None

        #cat representation
        if self.embed_cols_count>0:
            cat_reps = torch.zeros((non_text_input.shape[0],1,self.dim)).to(self.device)
            for i in range(self.embed_cols_count):
                embed_rep = self.embedding_layer[i](non_text_input[:,self.num_cols_count+i].to(torch.int)) #batch*dim
                cat_reps = torch.cat((cat_reps, embed_rep.unsqueeze(1)),dim=1)
            cat_reps = cat_reps[:,1:,:] #batch*9*dim
            # print(cat_reps.shape)
        else:
            cat_reps = None

        #topic representation
        if self.topic_num>0:
            topic_rep = self.topic_layer(non_text_input[:,-self.topic_num:]).unsqueeze(1)
            # print(topic_rep.shape)
        else:
            topic_rep = None

        non_none_tensors = [] # Check if each tensor is not None, and if so, add it to the list
        if text_rep is not None:
            non_none_tensors.append(text_rep)
        if num_reps is not None:
            non_none_tensors.append(num_reps)
        if cat_reps is not None:
            non_none_tensors.append(cat_reps)
        if topic_rep is not None:
            non_none_tensors.append(topic_rep)
        post_reps = torch.cat(non_none_tensors, dim=1) #batch*12*dim
        # print(final_rep.shape)

        # attentioned_rep, feature_att_score = self.attention_module(final_rep, text_rep) #batch*1*dim
        post_attentioned_rep, post_feature_att_score = self.attention_module(post_reps, self.task_embedding.expand(post_reps.shape[0], -1, -1))
        # print(self.task_embedding)
        # print(attentioned_rep.shape)

        ## user representation
        """
            item_author_cate_index                    2
            article_author_index                      1
            article_source_cate_index                 1
        """
        user_reps = torch.zeros((user_input.shape[0],1,self.dim)).to(self.device)
        for i in range(self.user_embed_cols_count):
            embed_rep = self.user_embedding_layer[i](user_input[i].to(torch.int)) #batch*dim
            user_reps = torch.cat((user_reps, embed_rep.unsqueeze(1)),dim=1)
        user_reps = user_reps[:,1:,:] #batch*9*dim
        # print(user_reps.shape)

        user_attentioned_rep, user_feature_att_score = self.attention_module(user_reps, self.task_embedding.expand(user_reps.shape[0], -1, -1))

        scores = torch.bmm(user_attentioned_rep, post_attentioned_rep.transpose(1, 2)).squeeze()
        # print(scores.shape)

        feature_att_score = torch.cat((post_feature_att_score, user_feature_att_score), dim=1)
        # print(feature_att_score.shape)

        return scores, feature_att_score, title_att_score
    
    def compute_loss(self, scores): ##BPR loss
        positive_scores, negative_scores = scores
        score_diff = positive_scores - negative_scores

        # Compute the BPR loss
        loss = -torch.log(torch.sigmoid(score_diff)).sum()

        # Add L2 regularization
        lambda_reg = 0.01
        reg_loss = lambda_reg * (torch.norm(positive_scores) + torch.norm(negative_scores))

        return loss + reg_loss
        
    # def decode_text(self, pos_text_token):
    #     text = []
    #     for token in pos_text_token:
    #         text.append(self.tokenizer.decode(token))
    #     return self.tokenizer.decode(token)
    
    # def generate_report(self, text, pos_preds, pos_title_att_scores, y_pos_len,pos_feature_att_scores, report_path):
    #     feature_list = ['text', 'sentiment', 'stock_code', 'item_author', 'article_author', 'article_source', 'month', 'year', 'eastmoney_robo_journalism', 'media_robo_journalism', 'SMA_robo_journalism', 'topic']
    #     report = pd.DataFrame({
    #         'text': text,
    #         'pred': pos_preds,
    #         'title_attention': list(pos_title_att_scores.cpu().detach().numpy()),
    #         'features': [feature_list]*y_pos_len,
    #         'feature_attention': list(pos_feature_att_scores.cpu().detach().numpy())
    #     })
    #     report.to_csv(report_path)


    def eval(self, eval_data:DataLoader, device, explain=False):
        with torch.no_grad():
            eval_loss = 0
            # metrics_vals = {type(k).__name__:torch.zeros(1).to(device) for k in self.evaluators}
            metrics_vals = {}
            preds, ys = torch.tensor([]), torch.tensor([])
            y_pos_len, pos_preds = 0, torch.tensor([])
            text, pos_feature_att_scores, pos_title_att_scores = [], torch.tensor([]).to(device), torch.tensor([]).to(device)
            for _, (x, y) in enumerate(eval_data):

                text_input, non_text_input = x
                
                text_input = text_input.to(device)
                non_text_input = non_text_input.to(device)
                y = y.squeeze().to(torch.long).to(device)

                pred, feature_att_score, title_att_score = self.forward(text_input, non_text_input)

                eval_loss += self.compute_loss(pred, y)

                ys = torch.cat((ys,y.cpu().detach()))
                pred = pred.cpu().detach().max(1).indices
                preds = torch.cat((preds, pred))
                # print(ys, preds)
                
                if explain: #record attention scores for analysis
                    y_pos_index = (y==1).nonzero().squeeze().cpu().detach()
                    # print('---------')
                    # print(y)
                    # print(y_pos_index)
                    # print(pred)
                    if y_pos_index.nelement() > 0:
                        y_pos_len += y_pos_index.nelement()
                        # print(y_pos_index)
                        # print(preds[y_pos_index])
                        if y_pos_index.nelement()==1:
                            y_pos_index = y_pos_index.unsqueeze(0)

                        pos_preds = torch.cat((pos_preds, pred[y_pos_index]))
                        # print(pos_preds)

                        pos_feature_att_score = feature_att_score[y_pos_index]
                        # print(pos_feature_att_score)
                        pos_feature_att_scores = torch.cat((pos_feature_att_scores, pos_feature_att_score), 0)
                        # print(pos_feature_att_scores)
                        
                        pos_title_att_score = title_att_score[y_pos_index]
                        # print(pos_title_att_score)
                        pos_title_att_scores = torch.cat((pos_title_att_scores, pos_title_att_score), 0)
                        # print(pos_title_att_scores)

                        pos_text_token = text_input[y_pos_index,0,:]
                        tokenizer = BertTokenizer.from_pretrained('bert-base-chinese')
                        for token in pos_text_token:
                            text.append(tokenizer.decode(token))
                        # print(text)

            for e in self.evaluators:
                metrics_vals[type(e).__name__] = e(ys, preds) #[1, task]

            # print(y_pos_len)
            # print(len(pos_preds))
            # print(pos_title_att_scores.shape)
            # print(len(text))
            # print(pos_feature_att_scores.shape)

            #generate analysis report
            if explain and len(text)>0:
                feature_list = ['text', 'sentiment', 'stock_code', 'item_author', 'article_author', 'article_source', 'month', 'year', 'eastmoney_robo_journalism', 'media_robo_journalism', 'SMA_robo_journalism', 'topic']
                report = pd.DataFrame({
                    'text': text,
                    'pred': pos_preds,
                    'title_attention': list(pos_title_att_scores.cpu().detach().numpy()),
                    'features': [feature_list]*y_pos_len,
                    'feature_attention': list(pos_feature_att_scores.cpu().detach().numpy())
                })
            else:
                print('no positive data, no report generated')
                report = None

            return eval_loss, metrics_vals, report