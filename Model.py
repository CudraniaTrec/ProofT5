import torch.nn as nn
import torch
from transformers import AutoConfig, AutoModel

class MyT5(nn.Module):
    def __init__(self, args):
        super(MyT5, self).__init__()
        config = AutoConfig.from_pretrained('Utils/models/' + args.pretrain_name) #grammart5-small
        self.model = AutoModel.from_config(config)

        args.embedding_size = self.model.config.hidden_size
        self.lm_head = nn.Linear(args.embedding_size, args.rulenum, bias=False)
        self.embedding_size = args.embedding_size
        self.mask_id = args.mask_id

        self.vocab_size = args.rulenum
        self.resize_token_embeddings(self.vocab_size)
    
    def resize_token_embeddings(self, new_num_tokens):
        self.model.encoder.resize_token_embeddings(new_num_tokens)
        self.model.set_input_embeddings(self.model.encoder.embed_tokens)
        self.lm_head.weight = self.model.decoder.embed_tokens.weight

    def forward(self, inputnl, inputrule):
        inputRes = inputrule[:, 1:].long()  # (batch_size, seq_len-1)
        inputrule = inputrule[:, :-1].long()# (batch_size, seq_len-1)
        rulemask = torch.ne(inputrule, self.mask_id)
        nlmask = torch.ne(inputnl, self.mask_id)

        encoder_outputs = self.model.encoder(inputnl.long(), attention_mask=nlmask)
        hidden_states = encoder_outputs.last_hidden_state
        output = self.model.decoder(inputrule, attention_mask=rulemask, encoder_hidden_states=hidden_states, encoder_attention_mask=nlmask)
        output = output.last_hidden_state
        output = self.lm_head(output * (self.embedding_size**-0.5))
        
        criterion = nn.CrossEntropyLoss(ignore_index=self.mask_id)
        output = output.view(-1, output.size(-1))  # shape: (batch_size * (seq_len-1), rulenum)
        inputRes = inputRes.reshape(-1)  # shape: (batch_size * (seq_len-1),)
        loss = criterion(output, inputRes)
        return loss, {}

    def test_forward(self, nlencode, nlmask, inputrule, past_key_values=None):
        output = self.model.decoder(inputrule, attention_mask=None, encoder_hidden_states=nlencode, encoder_attention_mask=nlmask, past_key_values=past_key_values)
        past_key_values = output.past_key_values
        output = output.last_hidden_state

        #tie-word-embedding
        output = output * (self.embedding_size**-0.5)
        resSoftmax = torch.softmax(self.lm_head(output), dim=-1)            
        return resSoftmax, past_key_values
    
    def encode_nl(self, inputnl):
        nlmask = torch.ne(inputnl, self.mask_id)
        encoder_outputs = self.model.encoder(inputnl, attention_mask=nlmask)
        return encoder_outputs.last_hidden_state, nlmask

# add coqview to back
class MyT5withCoq1(MyT5):
    def __init__(self, args):
        super(MyT5withCoq1, self).__init__(args)
        self.ff = nn.Linear(args.embedding_size * 2, args.embedding_size)
        self.relu = nn.ReLU()
        self.sigma1 = nn.Parameter(torch.tensor([0.0]))
        self.sigma2 = nn.Parameter(torch.tensor([0.0]))
    
    def combine_output(self, output, coqview):
        # output size: batchsize * rulelen * embedding_size
        # coqview size: batchsize * rulelen * coqviewlen
        batchsize = coqview.size(0)
        rulelen = coqview.size(1)
        coqview = coqview.view(-1, coqview.size(-1)) # size: (batchsize*rulelen) * coqviewlen
        # coqview_mask = torch.ne(coqview, self.mask_id)
        coqview_encode = self.model.encoder.embed_tokens(coqview) # （batchsize*rulelen）* coqview_len * embedding_size
        coqview_pooled = coqview_encode.mean(dim=1) # (batchsize*rulelen) * embedding_size

        output_combined = output.view(-1, self.embedding_size) # (batchsize*rulelen) * embedding_size
        output_combined = torch.cat([output_combined, coqview_pooled], dim=-1) # (batchsize*rulelen) * (2* embedding_size)
        output_combined = self.ff(output_combined) # (batchsize*rulelen) * embedding_size
        output_combined = self.relu(output_combined)
        output = output_combined.view(batchsize, rulelen, self.embedding_size) # batchsize * rulelen * embedding_size
        return output

    def forward(self, inputnl, inputrule, inputcoqview):
        inputRes = inputrule[:, 1:].long()  # (batch_size, seq_len-1)
        inputrule = inputrule[:, :-1].long()# (batch_size, seq_len-1)
        rulemask = torch.ne(inputrule, self.mask_id)
        nlmask = torch.ne(inputnl, self.mask_id)

        # get model output
        encoder_outputs = self.model.encoder(inputnl.long(), attention_mask=nlmask)
        hidden_states = encoder_outputs.last_hidden_state
        output = self.model.decoder(inputrule, attention_mask=rulemask, encoder_hidden_states=hidden_states, encoder_attention_mask=nlmask)
        output = output.last_hidden_state
        output = output * (self.embedding_size**-0.5) # size: (batch_size, seq_len-1, embedding_size)
        combined_output = self.combine_output(output, inputcoqview) # size: (batch_size, seq_len-1, embedding_size)
        combined_output = self.lm_head(combined_output) # size: (batch_size, seq_len-1, rulenum)
        output = self.lm_head(output) # size: (batch_size, seq_len-1, rulenum)

        # cal loss
        criterion = nn.CrossEntropyLoss(ignore_index=self.mask_id)
        combined_output = combined_output.view(-1, output.size(-1))  # shape: (batch_size * (seq_len-1), rulenum)
        output = output.view(-1, output.size(-1))
        inputRes = inputRes.reshape(-1)  # shape: (batch_size * (seq_len-1),)
        loss1 = criterion(output, inputRes)
        loss2 = criterion(combined_output, inputRes)
        # expSigma1 = torch.exp(self.sigma1)
        # expSigma2 = torch.exp(self.sigma2)
        # loss = (loss1 / expSigma1 + self.sigma1) + (loss2 / expSigma2 + self.sigma2)
        loss = 0.5 * loss1 + 0.5 * loss2
        return loss, {"loss1": loss1, "loss2": loss2, "sigma1": self.sigma1, "sigma2": self.sigma2}

    def test_forward(self, nlencode, nlmask, inputrule, inputcoqview=None, past_key_values=None):
        output = self.model.decoder(inputrule, attention_mask=None, encoder_hidden_states=nlencode, encoder_attention_mask=nlmask, past_key_values=past_key_values)
        past_key_values = output.past_key_values
        output = output.last_hidden_state
        output = output * (self.embedding_size**-0.5) # size: (batch_size, 1, embedding_size)
        if inputcoqview != None: # size: (batch_size, 1, coqview_len)
            combined_output = self.combine_output(output, inputcoqview) # size: (batch_size, 1, embedding_size)
            output = self.lm_head(0.5 * output + 0.5 * combined_output) # size: (batch_size, 1, rulenum)
        else:
            output = self.lm_head(output) # size: (batch_size, 1, rulenum)
        
        #tie-word-embedding
        resSoftmax = torch.softmax(output, dim=-1)            
        return resSoftmax, past_key_values

# add coqview tp the input
class MyT5withCoq2(MyT5):
    def __init__(self, args):
        super(MyT5withCoq2, self).__init__(args)

    def forward(self, inputnl, inputrule, inputcoqview):
        inputRes = inputrule[:, 1:].long()  # (batch_size, rule_len)
        inputrule = inputrule[:, :-1].long()# (batch_size, rule_len)
        rule_len = inputrule.size(1)
        batch_size = inputrule.size(0)
        rulemask = torch.ne(inputrule, self.mask_id)

        # get model output
        inputnl = inputnl.repeat_interleave(rule_len, dim=0) # (batch_size*rule_len, nl_len)
        inputcoqview = inputcoqview.view(-1, inputcoqview.size(-1)) # (batch_size*rule_len, coqview_len)
        inputnl = torch.cat([inputnl, inputcoqview], dim=-1) # (batch_size*rule_len, nl_len+coqview_len)
        inputnl = inputnl.view(batch_size, rule_len, -1) # (batch_size, rule_len, nl_len+coqview_len)
        inputnl = inputnl.transpose(0, 1) # (rule_len, batch_size, nl_len+coqview_len)

        past_kv = None
        crossentropy = nn.CrossEntropyLoss(ignore_index=self.mask_id)
        loss = 0
        for i in range(rule_len):
            input_stepi = inputnl[i] # input_stepi size: (batch_size, nl_len+coqview_len)
            stepi_mask = torch.ne(input_stepi, self.mask_id)
            encoder_outputs = self.model.encoder(input_stepi.long(), attention_mask=stepi_mask)
            hidden_states = encoder_outputs.last_hidden_state # size: (batch_size, nl_len+coqview_len, embedding_size)
            output = self.model.decoder(inputrule[:, i:i+1], attention_mask=rulemask[:, i:i+1], encoder_hidden_states=hidden_states, past_key_values=past_kv) 
            past_kv = output.past_key_values
            output = output.last_hidden_state # size: (batch_size, 1, embedding_size)
            output = output.squeeze(1) * (self.embedding_size**-0.5) # size: (batch_size, embedding_size)
            output = self.lm_head(output) # size: (batch_size, rulenum)
            standard_output = inputRes[:, i] # size: (batch_size,)
            loss += crossentropy(output, standard_output)
        return loss, {}

    def test_forward(self, nlencode, nlmask, inputrule, inputcoqview, past_key_values=None):
        inputnl = nlencode # size: (batch_size, nl_len)
        inputcoqview = inputcoqview.squeeze(1) # size: (batch_size, coqview_len)
        inputnl = torch.cat([inputnl, inputcoqview], dim=-1) # (batch_size, nl_len+coqview_len)
        input_mask = torch.ne(inputnl, self.mask_id)
        hidden_states = self.model.encoder(inputnl.long(), attention_mask=input_mask).last_hidden_state 
        # size: (batch_size, nl_len+coqview_len, embedding_size)
        output = self.model.decoder(inputrule, attention_mask=None, encoder_hidden_states=hidden_states, encoder_attention_mask=input_mask, past_key_values=past_key_values)
        past_key_values = output.past_key_values
        output = output.last_hidden_state * (self.embedding_size**-0.5) # size: (batch_size, 1, embedding_size)
        
        #tie-word-embedding
        resSoftmax = torch.softmax(self.lm_head(output), dim=-1)            
        return resSoftmax, past_key_values

    def encode_nl(self, inputnl):
        return inputnl, None