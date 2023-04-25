#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""attention model performance

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1WgURLu-n4R0ipX6svtudW0XS90ZaDapZ
"""

# Load the required libraries
import pandas as pd
# import numpy as np
# from sklearn.feature_extraction.text import CountVectorizer
# from sklearn.decomposition import LatentDirichletAllocation

import torch
from transformers import BertTokenizer, BertForSequenceClassification, BertConfig
# from transformers import AutoTokenizer, AutoModelForSequenceClassification
# from transformers import Trainer, TrainingArguments
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

import logging
LOG_PATH = (f"./logs/att_performance.log")
logging.basicConfig(filename=LOG_PATH, filemode='w', level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


df = pd.read_csv('./data/news_data_with_y1030_sentiment.csv')

# config variables
mode = 'train'
percent = 30 

device = 'cuda' # changable
if device == 'cuda' and torch.cuda.is_available():
    device = torch.device('cuda')
elif device == 'mps' and torch.backends.mps.is_available(): # type: ignore
    device = torch.device('mps')
else:
    device = torch.device('cpu')
logging.debug(f"Computing device: {device}")

# add dropout
configuration = BertConfig.from_pretrained('bert-base-chinese', num_labels=2, output_hidden_states=True, output_attentions=True)
configuration.hidden_dropout_prob = 0.8
configuration.attention_probs_dropout_prob = 0.8
logging.debug(configuration)

model = BertForSequenceClassification.from_pretrained('bert-base-chinese', config=configuration)
criterion = torch.nn.CrossEntropyLoss()

# Tokenize the input text and convert it to PyTorch tensors
tokenizer = BertTokenizer.from_pretrained('bert-base-chinese')
input_ids = []
attention_masks = []
for text in df['Item_Title']:
    encoded_dict = tokenizer.encode_plus(text,
                                          add_special_tokens=True,
                                          max_length=64,
                                          pad_to_max_length=True,
                                          return_attention_mask=True,
                                          return_tensors='pt')
    input_ids.append(encoded_dict['input_ids'])
    attention_masks.append(encoded_dict['attention_mask'])

input_ids = torch.cat(input_ids, dim=0)
attention_masks = torch.cat(attention_masks, dim=0)
labels = torch.tensor(df[f'top{percent}p_views'].values)

train_inputs, validation_inputs, train_labels, validation_labels = train_test_split(input_ids, labels, random_state=42, test_size=0.1)
train_masks, validation_masks, _, _ = train_test_split(attention_masks, input_ids, random_state=42, test_size=0.1)

# Define the training parameters
batch_size = 16
epochs = 5
learning_rate = 1e-6

# Train the model
if mode == 'test':

    # Load the pre-trained tokenizer and model
    model.to(device)

    # Define the optimizer and loss function
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    logging.debug("Enter Traning")
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for i in range(0, len(train_inputs), batch_size):
            inputs = train_inputs[i:i+batch_size]
            masks = train_masks[i:i+batch_size]
            labels = train_labels[i:i+batch_size]

            inputs = inputs.to(device)
            masks = masks.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()

            outputs = model(inputs, attention_mask=masks, labels=labels)
            output_logit = outputs[1].softmax(dim=1)
            print(output_logit, labels)
            loss = criterion(output_logit, labels)
            print(loss)

            train_loss += loss.item()

            loss.backward()
            optimizer.step()
            if i%10000==0:
                logging.debug(f"train:{i}")
        logging.debug(f"train epoch:{epoch}, loss:{train_loss}")

        torch.save(model.state_dict(),f"./models/attention_model_{percent}_{epoch}_sig.pt")

    #     # Evaluate the model on the validation set
    #     model.eval()
    #     eval_loss = 0
    #     num_correct = 0
    #     predictions = []
    #     true_labels = []
    #     attention_weights = []
    #     with torch.no_grad():
    #         for i in range(0, len(validation_inputs), batch_size):
    #             inputs = validation_inputs[i:i+batch_size]
    #             masks = validation_masks[i:i+batch_size]
    #             labels = validation_labels[i:i+batch_size]

    #             inputs = inputs.to(device)
    #             masks = masks.to(device)
    #             labels = labels.to(device)


    #             outputs = model(inputs, attention_mask=masks, labels=labels)
    #             loss = criterion(outputs[1], labels)

    #             eval_loss += loss.item()

    #             _, preds = torch.max(outputs[1], dim=1)
    #             num_correct += torch.sum(preds == labels)
    #             predictions.extend(preds.cpu().numpy().tolist())
    #             true_labels.extend(labels.cpu().numpy().tolist())
                
    #             # Get attention weights
    #             attention_weight = []
    #             for j in range(len(inputs)):
    #                 input_ids = inputs[j]
    #                 attention_mask = masks[j]
    #                 output = model(input_ids.unsqueeze(0), attention_mask=attention_mask.unsqueeze(0))
    #                 attn_weights = torch.softmax(output.attentions[-1][0], dim=-1)
    #                 attn_weights = attn_weights.squeeze()
    #                 attention_weight.append(attn_weights.cpu().numpy().tolist())
    #             attention_weights.extend(attention_weight)
    #             if i%10000==0:
    #                 logging.debug(f"test:{i}")
            

    # # Calculate the accuracy and logging.debug the results
    # accuracy = num_correct / len(validation_labels)
    # logging.debug(f'Epoch {epoch + 1}/{epochs}, Training Loss: {train_loss / len(train_labels):.4f}, Validation Loss: {eval_loss / len(validation_labels):.4f}, Validation Accuracy: {accuracy:.4f}')

    # # logging.debug classification report and confusion matrix
    # logging.debug(f"\n{classification_report(true_labels, predictions)}")
    # confusion_matrix = pd.crosstab(pd.Series(true_labels), pd.Series(predictions), rownames=['True'], colnames=['Predicted'])
    # logging.debug(f"\n{confusion_matrix}")
    # confusion_matrix.to_csv('./att_results/confusion matrix.csv', index=False)
    # # Save attention weights to a CSV file
    # attention_df = pd.DataFrame({'text': validation_inputs.cpu().numpy().tolist(),
    #                             'label': true_labels,
    #                             'prediction': predictions,
    #                             'attention_weights': attention_weights})
    # attention_df.to_csv('./att_results/attention_weights.csv', index=False)


elif mode == 'test':
    logging.debug("enter testing mode")
    for epoch in range(epochs):
        logging.debug(f"{epoch}")
        param = torch.load(f"./models/attention_model_{percent}_{epoch}.pt")
        model.load_state_dict(param)
        model.to(device)
        logging.debug(f"data size: {len(validation_inputs)}")

        # Evaluate the model on the validation set
        model.eval()
        batch_size = 1
        eval_loss = 0
        num_correct = 0
        predictions = []
        true_labels = []
        attention_weights = []
        with torch.no_grad():
            for i in range(0, len(validation_inputs),batch_size):
                inputs = validation_inputs[i:i+batch_size]
                masks = validation_masks[i:i+batch_size]
                labels = validation_labels[i:i+batch_size]

                inputs = inputs.to(device)
                masks = masks.to(device)
                labels = labels.to(device)


                outputs = model(inputs, attention_mask=masks, labels=labels)
                loss = criterion(outputs[1], labels)

                attn_weights = torch.softmax(outputs.attentions[-1][0], dim=-1).squeeze()
                attn_value = torch.unsqueeze(attn_weights, 0)

                eval_loss += loss.item()

                _, preds = torch.max(outputs[1], dim=1)
                # print(outputs[1])
                # print(labels)
                num_correct += torch.sum(preds == labels)
                predictions.extend(preds.cpu().numpy().tolist())
                true_labels.extend(labels.cpu().numpy().tolist())
                
                # Get attention weights
                # attention_weight = []
                # for j in range(len(inputs)):
                #     input_ids = inputs[j]
                #     attention_mask = masks[j]
                #     output = model(input_ids.unsqueeze(0), attention_mask=attention_mask.unsqueeze(0))
                #     attn_weights = torch.softmax(output.attentions[-1][0], dim=-1)
                #     attn_weights = attn_weights.squeeze()
                #     attention_weight.append(attn_weights.cpu().numpy().tolist())
                # attention_weights.extend(attention_weight)
                # print(validation_inputs.cpu().numpy().tolist())
                # print(inputs.shape, labels.shape, preds.shape, attn_value.shape) 
                attention_df = pd.Series({'text': inputs.cpu().numpy(),
                                    'label': labels.cpu().numpy(),
                                    'prediction': preds.cpu().numpy(),
                                    'attention_weights': attn_value.cpu().numpy()})
                attention_df.to_frame().T.to_csv(f'./att_results/attention_weights_{percent}_{epoch}.csv', mode='a', index=False, header=False)
                # del attn_weights
                # del attention_df
                # break
                if i%10000==0:
                    logging.debug(f"test:{i}")
                

        # Calculate the accuracy and logging.debug the results
        accuracy = num_correct / len(validation_labels)
        logging.debug(f'Validation Loss: {eval_loss / len(validation_labels):.4f}, Validation Accuracy: {accuracy:.4f}')

        # logging.debug classification report and confusion matrix
        logging.debug(f"\n{classification_report(true_labels, predictions)}")
        confusion_matrix = pd.crosstab(pd.Series(true_labels), pd.Series(predictions), rownames=['True'], colnames=['Predicted'])
        logging.debug(f"\n{confusion_matrix}")
        confusion_matrix.to_csv(f'./att_results/confusion matrix_{percent}_{epoch}.csv', index=False)
        # Save attention weights to a CSV file
        # attention_df = pd.DataFrame({'text': validation_inputs.cpu().numpy().tolist(),
        #                             'label': true_labels,
        #                             'prediction': predictions,
        #                             'attention_weights': attention_weights})
        # attention_df.to_csv('./att_results/attention_weights.csv', mode='a', index=False, header=False)