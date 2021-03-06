from click import echo, prompt
import os
import yaml
import json
from ..ega.entities import Dac, Policy, Contact, Study, Submission, SubmissionSubsetData
from ..ega.services import login, logout, object_submission, query_by_type, prepare_submission
from ..exceptions import CredentialsError


def init_workspace(ctx,ega_submitter_account=None,ega_submitter_password=None,icgc_id_service_token=None,icgc_project_code=None):
    ctx.obj['LOGGER'].info('Initalizing EGA submission workspace...')
    ctx.obj['LOGGER'].info('Note: information collected below will be stored in')
    ctx.obj['LOGGER'].info('      \'.egasub/config.yaml\' which can be edited later.')
    
    projects = ["BLCA-CN","BOCA-FR","BOCA-UK","BRCA-EU","BRCA-FR","BRCA-KR","BRCA-UK","BTCA-JP","BTCA-SG","CLLE-ES","CMDI-UK",
            "COCA-CN","EOPC-DE","ESAD-UK","ESCA-CN","GACA-CN","LAML-CN","LAML-KR",
            "LIAD-FR","LICA-CN","LICA-FR","LIHM-FR","LINC-JP","LIRI-JP","LUSC-CN","LUSC-KR","MALY-DE","MELA-AU","ORCA-IN","OV-AU",
            "PACA-AU","PACA-CA","PAEN-AU","PAEN-IT","PBCA-DE","PRAD-CA","PRAD-UK","RECA-CN","RECA-EU","SKCA-BR","THCA-SA",
        ]
    
    #Ask user input for config.yaml
    if not ega_submitter_account:
        ega_submitter_account = prompt("Enter your EGA submitter account", default='')
    if not ega_submitter_password:
        ega_submitter_password = prompt("Enter your EGA submitter password", default='', hide_input=True)
    if not icgc_id_service_token:
        icgc_id_service_token = prompt("Enter your ICGC ID service token", default='')
    if not icgc_project_code:
        while True:
            icgc_project_code = prompt("Enter your ICGC project code", default='')
            if icgc_project_code.upper() in projects:
                break
            else:
                echo("Please enter a project from the following list:")
                echo('\t'.join(projects))
        
    yaml_info = {
        'ega_submitter_account': ega_submitter_account,
        'ega_submitter_password': ega_submitter_password,
        'icgc_id_service_token': icgc_id_service_token,
        'icgc_project_code': icgc_project_code.upper()
        }
    
    ctx.obj['LOGGER'].info("EGA and ICGC credentials collected")

    initialize_dac_policy_study(ctx, yaml_info, ega_submitter_account, ega_submitter_password)

    current_dir = ctx.obj['CURRENT_DIR']
    egasub_dir = os.path.join(current_dir,'.egasub')
    script_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    
    if os.access(current_dir, os.W_OK):
        os.mkdir(egasub_dir)
        ctx.obj['LOGGER'].info("Creation of .egasub directory")
        
        with open(os.path.join(egasub_dir,'config.yaml'),'w') as outfile:
            yaml.safe_dump(yaml_info,outfile,default_flow_style=False)
            
        ctx.obj['LOGGER'].info("Credentials added to .egasub/config.yaml file")

        ctx.obj['LOGGER'].info('EGA submission workspace initialized')
        
    else:
        ctx.obj['LOGGER'].critical('Permission denied on directory '+current_dir)


def initialize_dac_policy_study(ctx, yaml_info, ega_submitter_account, ega_submitter_password):
    """
    Function to create dummy Dac and Policy, and associate existing EGA study with
    the EGA submission workspace to be initialized. Will create new EGA study if none exists 
    """
    if not ctx.obj.get('SETTINGS'):
        ctx.obj['SETTINGS'] = {}

    ctx.obj['SETTINGS']['ega_submitter_account'] = ega_submitter_account
    ctx.obj['SETTINGS']['ega_submitter_password'] = ega_submitter_password

    try:
        login(ctx)
    except CredentialsError as error:
        ctx.obj['LOGGER'].critical("Login failed: %s" % str(error))
        ctx.abort()

    ctx.obj['LOGGER'].info("Login success")
    submission = Submission('title', 'a description',SubmissionSubsetData.create_empty())
    prepare_submission(ctx, submission)

    # query for existing studies
    studies = query_by_type(ctx, 'study', obj_status="SUBMITTED")
    study_alias = None
    study_id = None
    if studies:
        echo("Study ID\tAlias\tStudy Type\tTitle")
        echo("-----------------------------------------------")
        parse_dict = []
        i=1
        for study in studies:
            parse_dict.append({'index':i,'alias':study['alias'],'studyType':study['studyType'],'title':study['title'],'studyAbstract':study['studyAbstract'],'studyTypeId':study['studyTypeId'],'studyId':study['id'],'shortName':study['shortName']})
            echo(str(i)+". "+study['id']+"\t"+study['alias']+"\t"+study['studyType']+"\t"+study['title'])
            i+=1
        echo("-----------------------------------------------")

        while True:
            study_key = prompt("Select an existing study or enter 0 to create a new study: ", default=0)
            if study_key >= 0 and study_key <= len(parse_dict):
                break

        if study_key != 0:
            for study in parse_dict:
                if study['index'] == study_key:
                    echo(study['alias']+" selected")
                    study_alias = study['alias']
                    study_id = study['studyId']
                    break

    if not (study_alias and study_id):
        echo("Please enter the following to create a new EGS study.")
        study_alias = prompt("Study alias (required)")
                
        study_types = ctx.obj['EGA_ENUMS'].__dict__['_enums']['study_types']['response']['result']
        ids = [dataset['tag'] for dataset in study_types]
        values = [dataset['value'] for dataset in study_types]
        for i in xrange(0,len(values)):
            echo(ids[i]+"\t- "+values[i])

        while True:
            study_type_id = prompt("Study type ID (required, 8 for Cancer Genomics)", default=8)
            if study_type_id >=0 and study_type_id <= len(study_types):
                break

        study_title = prompt("Study title (required)")
        study_abstract = prompt("Study abstract (required)")
        study_short_name = prompt("Short study name", default="")
        study = Study(
            study_alias, # alias
            study_type_id, # studyTypeId, Cancer Genomics
            study_short_name, # should take it from config
            study_title, # should take it from config
            study_abstract, # should take it from config
            None,  # ownTerm
            [],  # pubMedIds
            [],   # customTags
            None
        )
        object_submission(ctx, study, 'study', dry_run=False)

        study_alias = study.alias
        study_id = study.id

    yaml_info['ega_study_alias'] = study_alias
    yaml_info['ega_study_id'] = study_id

    # new create dac and policy
    dac = make_dummy_dac()
    object_submission(ctx, dac, 'dac', dry_run=False)

    policy = make_dummy_policy(dac.id)
    object_submission(ctx, policy, 'policy', dry_run=False)

    yaml_info['ega_policy_id'] = policy.id


# EGA REST API based submission does not handle this properly yet,
# we were advised to create dummy Dac and Policy object to get things started 
def make_dummy_dac():
    return Dac(
            "ICGC DACO",
            [Contact("Helpdesk", "dcc-support@icgc.org", "ICGC", "")],
            "ICGC DACO"
        )

def make_dummy_policy(dac_id):
    return Policy(
            "ICGC Data Access Agreements",
            dac_id,
            'ICGC Data Access',
            'Please use the ICGC website for applying access to the data',
            'http://www.icgc.org'
        )

