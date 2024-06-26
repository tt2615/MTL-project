import pandas as pd
import numpy as np

import torch
torch.manual_seed(666)
from torch.utils.data import Dataset

from transformers import BertTokenizer

class BertData(Dataset):
    def __init__(self, cat_cols=[], num_cols=[], topic_cols=[], tar_cols=[], max_padding_len=32, dir="./data/eastmoney_topic_bert.csv", x_transforms=None, y_transforms=None, bert='bert-base-chinese'):

        #load data
        self.data = pd.read_csv(dir,index_col=0, nrows=64000)
        # print(self.data.columns)
        # print(self.data.dtypes)

        # #generate onehot encoding
        # self.data = pd.get_dummies(self.data, columns=onehot_cols)

        # process cat cols: generate embed index for embed cols
        self.data[cat_cols] = self.data[cat_cols].apply(lambda c: c.astype('category'))
        self.embed_cols = []
        for cat_col in cat_cols:
            self.data[f'{cat_col}_index'] = self.data[cat_col].cat.codes+1 #+1 for nan cases
            self.embed_cols.append(f'{cat_col}_index')

        # process text data: for bert input 
        tokenizer = BertTokenizer.from_pretrained(bert)
        input_ids = []
        attention_masks = []
        for text in self.data['item_title']:
            encoded_dict = tokenizer.encode_plus(text,
                                                add_special_tokens=True,
                                                max_length=max_padding_len,
                                                truncation=True,
                                                padding='max_length',
                                                return_attention_mask=True,
                                                return_tensors='pt')
            input_ids.append(np.array(encoded_dict['input_ids'].squeeze()))
            attention_masks.append(np.array(encoded_dict['attention_mask'].squeeze()))
            # print(text)
            # print(encoded_dict['input_ids'])
        self.data['title_id'] = input_ids
        self.data['title_mask'] = attention_masks

        self.text_cols=['title_id', 'title_mask']
            
        self.num_cols = num_cols
        self.topic_cols = topic_cols
        self.tar_cols = tar_cols

        # print(self.data.dtypes)

        self.x_trans_list = x_transforms
        self.y_trans_list = y_transforms

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        record = self.data.iloc[idx]
        text_input = record[self.text_cols]
        non_text_input = record[self.num_cols+self.embed_cols+self.topic_cols].astype(np.float32)
        # print(non_text_input)
        y = record[self.tar_cols]

        if self.x_trans_list:
            for trsfm in self.x_trans_list:
                text_input = np.stack(text_input.values)
                text_input = trsfm(text_input)
                non_text_input = trsfm(non_text_input)
        if self.y_trans_list:
            for trsfm in self.y_trans_list:
                y = trsfm(y)

        # print(text_input)
        # print(non_text_input)
        # print(y)
        
        return (text_input, non_text_input), y
    
    def get_task_num(self):
        return len(self.tar_cols)
    
    def get_embed_feature_unique_count(self):
        return [self.data[x].nunique()+1 for x in self.embed_cols]
    
    def get_num_feature_count(self):
        return len(self.num_cols)

    def get_topic_num(self):
        return len(self.topic_cols)
    
    def get_embed_feature_count(self):
        return len(self.embed_cols)
    
    def get_pos_data(self):
        pos_data = self.data[self.data['viral']==1]
        return pos_data
    
    def get_class_count(self):
        return self.data['viral'].value_counts()