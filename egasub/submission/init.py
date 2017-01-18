from click import echo
from click import prompt
import os
import yaml
import shutil

def init_workspace(ctx):
    echo('Initalizing EGA submission workspace...')
    #Ask user input for config.yaml
    yaml_info = {
        'ega_submitter_account':prompt("Enter your EGA submitter account"),
        'ega_submitter_password':prompt("Enter your EGA submitter password",hide_input=True)
        }
    
    current_dir = ctx.obj['CURRENT_DIR']
    egasub_dir = os.path.join(current_dir,'.egasub')
    script_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    
    if os.access(current_dir, os.W_OK):
        os.mkdir(egasub_dir)
        
        policy_dir = os.path.join(current_dir,'policy')
        
        with open(os.path.join(egasub_dir,'config.yaml'),'w') as outfile:
            yaml.safe_dump(yaml_info,outfile,default_flow_style=False)
            
        shutil.copytree(os.path.join(script_dir,"ega","data","policy"),policy_dir)
        echo('EGA submission workspace initialized')
        
    else:
        echo('Permission denied on directory '+current_dir)