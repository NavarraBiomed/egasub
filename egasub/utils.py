import os
import re
import yaml
import glob
import ftplib
from click import echo
from egasub.ega.entities.file import File
import logging
import datetime
from egasub.ega.entities import EgaEnums



def initialize_app(ctx):
    if not ctx.obj['WORKSPACE_PATH']:
        ctx.obj['LOGGER'].critical('Not in an EGA submission workspace! Please run "egasub init" to initiate an EGA workspace.')
        ctx.abort()

    #echo('Info: workspace is \'%s\'' % ctx.obj['WORKSPACE_PATH'])

    # read the settings
    ctx.obj['SETTINGS'] = get_settings(ctx.obj['WORKSPACE_PATH'])
    if not ctx.obj['SETTINGS']:
        ctx.obj['LOGGER'].critical('Unable to read config file, or config file invalid!')
        ctx.abort()

    # figure out the current dir type, e.g., study, sample or analysis
    ctx.obj['CURRENT_DIR_TYPE'] = get_current_dir_type(ctx)
    #echo('Info: submission data type is \'%s\'' % ctx.obj['CURRENT_DIR_TYPE'])  # for debug
    if not ctx.obj['CURRENT_DIR_TYPE']:
        ctx.obj['LOGGER'].critical('The current working directory does not associate with any supported EGA data types: unaligned|alignment|variation')
        ctx.abort()
        
    ctx.obj['EGA_ENUMS'] = EgaEnums()
        
def initialize_log(ctx, debug, info):
    logger = logging.getLogger('ega_submission')
    logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
    
    if debug:
        logger.setLevel(logging.DEBUG)
    elif info:
        logger.setLevel(logging.INFO) 
    
    if ctx.obj['WORKSPACE_PATH'] == None:
        logger = logging.getLogger('ega_submission')
        ch = logging.StreamHandler()
        logger.addHandler(ch)
        ctx.obj['LOGGER'] = logger
        return
    
    log_directory = os.path.join(ctx.obj['WORKSPACE_PATH'],".log")
    log_file = os.path.join(log_directory,"%s.log" % re.sub(r'[-:.]', '_', datetime.datetime.utcnow().isoformat()))
    
    if not os.path.isdir(log_directory):
        os.mkdir(log_directory)
        
    fh = logging.FileHandler(log_file)
    fh.setFormatter(logFormatter)
    
    ch = logging.StreamHandler()
    ch.setFormatter(logFormatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    ctx.obj['LOGGER'] = logger

def find_workspace_root(cwd=os.getcwd()):
    searching_for = set(['.egasub'])
    last_root    = cwd
    current_root = cwd
    found_path   = None
    while found_path is None and current_root:
        for root, dirs, _ in os.walk(current_root):
            if not searching_for - set(dirs):
                # found the directories, stop
                return root
            # only need to search for the current dir
            break

        # Otherwise, pop up a level, search again
        last_root    = current_root
        current_root = os.path.dirname(last_root)

        # stop if it's already reached os root dir
        if current_root == last_root: break
    return None


def get_settings(wspath):
    config_file = os.path.join(wspath, '.egasub', 'config.yaml')
    if not os.path.isfile(config_file):
        return None

    with open(config_file, 'r') as f:
        settings = yaml.load(f)

    return settings


def get_current_dir_type(ctx):
    workplace = ctx.obj['WORKSPACE_PATH']
    current_dir = ctx.obj['CURRENT_DIR']

    pattern = re.compile('%s/(unaligned|alignment|variation)\.' % workplace)
    m = re.match(pattern, current_dir)
    if m and m.group(1):
        return m.group(1)

    return None


def file_pattern_exist(dirname, pattern):
    files = [f for f in os.listdir(dirname) if os.path.isfile(f)]
    for f in files:
        if re.match(pattern, f): return True

    return False


def ftp_files(path, ctx):
    host = ctx.obj['SETTINGS']['ftp_server']
    _, user, passwd = ctx.obj['AUTH'].split('%20') if len(ctx.obj['AUTH'].split('%20')) == 3 else ('', '', '')

    ftp = ftplib.FTP(host, user, passwd)

    files = []
    try:
        files = ftp.nlst(path)
    except ftplib.error_perm, resp:
        echo('Error: unable to connect to FTP server.', err=True)
        ctx.abort()

    return files

