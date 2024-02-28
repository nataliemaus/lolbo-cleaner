import sys
sys.path.append("../")
import fire
from lolbo_scripts.optimize import Optimize
from lolbo.info_transformer_vae_objective import InfoTransformerVAEObjective
import math 
import pandas as pd 
import torch 
import math 


class InfoTransformerVAEOptimization(Optimize):
    """
    Run LOLBO Optimization with InfoTransformerVAE 
    Args:
        path_to_vae_statedict: Path to state dict of pretrained VAE,
        max_string_length: Limit on string length that can be generated by VAE 
            (without a limit we can run into OOM issues)
        dim: dimensionality of latent space of VAE
        constraint1_min_threshold: min allowed value for constraint 1 (None --> unconstrained)
        constraint2_max_threshold: max allowed value for constraint 2 (None --> unconstrained)
    """
    def __init__(
        self,
        path_to_vae_statedict: str="../uniref_vae/saved_models/dim512_k1_kl0001_acc94_vivid-cherry-17_model_state_newest.pkl",
        dim: int=1024,
        task_specific_args: list=[], # list of additional args to be passed into objective funcion 
        max_string_length: int=150,
        constraint_function_ids: list=[], # list of strings identifying the black box constraint function to use
        constraint_thresholds: list=[], # list of corresponding threshold values (floats)
        constraint_types: list=[], # list of strings giving correspoding type for each threshold ("min" or "max" allowed)
        init_data_path: str="../initialization_data/example_init_data.csv",
        **kwargs,
    ):
        self.path_to_vae_statedict = path_to_vae_statedict
        self.dim = dim 
        self.max_string_length = max_string_length
        self.task_specific_args = task_specific_args 
        self.init_data_path = init_data_path
        # To specify constraints, pass in 
        #   1. constraint_function_ids: a list of constraint function ids, 
        #   2. constraint_thresholds: a list of thresholds, 
        #   3. constraint_types: a list of threshold types (must be "min" or "max" for each)
        # Empty lists indicate that the problem is unconstrained, 1 or more constraints can be added 
        assert len(constraint_function_ids) == len(constraint_thresholds)
        assert len(constraint_thresholds) == len(constraint_types)
        self.constraint_function_ids = constraint_function_ids # list of strings identifying the black box constraint function to use
        self.constraint_thresholds = constraint_thresholds # list of corresponding threshold values (floats)
        self.constraint_types = constraint_types # list of strings giving correspoding type for each threshold ("min" or "max" allowed)
        
        super().__init__(**kwargs) 

        # add args to method args dict to be logged by wandb 
        self.method_args['opt1'] = locals()
        del self.method_args['opt1']['self']


    def initialize_objective(self):
        # initialize objective 
        self.objective = InfoTransformerVAEObjective(
            task_id=self.task_id, # string id for your task
            task_specific_args=self.task_specific_args, # list of additional args to be passed into objective funcion 
            path_to_vae_statedict=self.path_to_vae_statedict, # state dict for VAE to load in
            max_string_length=self.max_string_length, # max string length that VAE can generate
            dim=self.dim, # dimension of latent search space
            constraint_function_ids=self.constraint_function_ids, # list of strings identifying the black box constraint function to use
            constraint_thresholds=self.constraint_thresholds, # list of corresponding threshold values (floats)
            constraint_types=self.constraint_types, # list of strings giving correspoding type for each threshold ("min" or "max" allowed)
        )
        # if train zs have not been pre-computed for particular vae, compute them 
        #   by passing initialization selfies through vae 
        self.init_train_z = self.compute_train_zs()
        # compute initial constriant values
        self.init_train_c = self.objective.compute_constraints(self.init_train_x)

        return self

    def compute_train_zs(
        self,
        bsz=32
    ):
        init_zs = []
        # make sure vae is in eval mode 
        self.objective.vae.eval() 
        n_batches = math.ceil(len(self.init_train_x)/bsz)
        for i in range(n_batches):
            xs_batch = self.init_train_x[i*bsz:(i+1)*bsz] 
            zs, _ = self.objective.vae_forward(xs_batch)
            init_zs.append(zs.detach().cpu())
        init_zs = torch.cat(init_zs, dim=0)

        return init_zs


    def load_train_data(self):
        ''' Load in or randomly initialize self.num_initialization_points
            total initial data points to kick-off optimization 
            Must define the following:
                self.init_train_x (a list of x's)
                self.init_train_y (a tensor of scores/y's)
        '''
        df = pd.read_csv(self.init_data_path)

        x = df["x"].values.tolist()  
        x = x[0:self.num_initialization_points] 

        y = torch.from_numpy(df["y"].values ).float()
        y = y[0:self.num_initialization_points] 
        y = y.unsqueeze(-1) 

        self.init_train_x = x
        self.init_train_y = y 
        
        return self 


if __name__ == "__main__":
    fire.Fire(InfoTransformerVAEOptimization)