import os
import click
import utils
from click import echo
from submission import init_workspace, perform_submission, init_submission_dir, generate_report, submit_dataset
from egasub.ega.entities import EgaEnums


@click.group()
@click.option('--debug/--no-debug', '-d', default=False)
@click.option('--info/--no-info','-i',default=True)
@click.pass_context
def main(ctx, debug, info):
    # initializing ctx.obj
    ctx.obj = {}
    ctx.obj['IS_TEST'] = False
    ctx.obj['CURRENT_DIR'] = os.getcwd()
    ctx.obj['IS_TEST_PROJ'] = None
    ctx.obj['WORKSPACE_PATH'] = utils.find_workspace_root(cwd=ctx.obj['CURRENT_DIR'])
    utils.initialize_log(ctx, debug, info)


@main.command()
@click.argument('submission_dir', type=click.Path(exists=True), nargs=-1)
@click.pass_context
def submit(ctx, submission_dir):
    """
    Perform submission on submission folder(s).
    """
    if '.' in submission_dir or '..' in submission_dir:
        ctx.obj['LOGGER'].critical("Submission dir can not be '.' or '..'")
        ctx.abort()

    utils.initialize_app(ctx)

    if not ctx.obj.get('WORKSPACE_PATH'):
        ctx.obj['LOGGER'].critical('Not in an EGA submission workspace %s' % ctx.obj['WORKSPACE_PATH'])
        ctx.abort()

    if not submission_dir:
        ctx.obj['LOGGER'].critical('You must specify at least one submission directory.')
        ctx.abort()

    perform_submission(ctx, submission_dir, dry_run=False)

@main.command()
@click.argument('submission_dir', type=click.Path(exists=True), nargs=-1)
@click.pass_context
def dry_run(ctx, submission_dir):
    """
    Test submission on submission folder(s).
    """
    if '.' in submission_dir or '..' in submission_dir:
        ctx.obj['LOGGER'].critical("Submission dir can not be '.' or '..'")
        ctx.abort()

    utils.initialize_app(ctx)

    if not submission_dir:
        ctx.obj['LOGGER'].critical('You must specify at least one submission directory.')
        ctx.abort()

    perform_submission(ctx, submission_dir, dry_run=True)


@main.command()
@click.argument('submission_dir', type=click.Path(exists=True), nargs=-1)
@click.pass_context
def status(ctx, submission_dir):
    """
    Report status of submission folder(s).
    """
    if '.' in submission_dir or '..' in submission_dir:
        ctx.obj['LOGGER'].critical("Submission dir can not be '.' or '..'")
        ctx.abort()

    utils.initialize_app(ctx)

    generate_report(ctx, submission_dir)


@main.command()
@click.option('--ega_submitter_account')
@click.option('--ega_submitter_password')
@click.option('--icgc_id_service_token')
@click.option('--icgc_project_code')
@click.pass_context
def init(ctx,ega_submitter_account,ega_submitter_password,icgc_id_service_token,icgc_project_code):
    """
    Run once to create a submission workspace.
    """

    if ctx.obj.get('WORKSPACE_PATH'):
        ctx.obj['LOGGER'].critical('Already in an EGA submission workspace %s' % ctx.obj['WORKSPACE_PATH'])
        ctx.abort()

    ctx.obj['EGA_ENUMS'] = EgaEnums()
    init_workspace(ctx,ega_submitter_account,ega_submitter_password,icgc_id_service_token,icgc_project_code )
    

@main.command()
@click.argument('submission_dir', type=click.Path(exists=True), nargs=-1)
@click.pass_context
def new(ctx,submission_dir):
    """
    Initialize new submission folders.
    """

    if '.' in submission_dir or '..' in submission_dir:
        ctx.obj['LOGGER'].critical("Submission dir can not be '.' or '..'")
        ctx.abort()

    utils.initialize_app(ctx)
    
    init_submission_dir(ctx, submission_dir)
    
@main.command()
@click.option('--submit', '-s', is_flag=True)
@click.option('--dry_run', '-d', is_flag=True)
@click.pass_context
def dataset(ctx,submit,dry_run):
    """
    Submit or test a dataset submissoin.
    """
    utils.initialize_app(ctx)
    
    if submit:
        submit_dataset(ctx, dry_run=False)
    elif dry_run:
        submit_dataset(ctx, dry_run=True)
    else:
        ctx.obj['LOGGER'].error("You must choose one of the options: --submit or --dry_run")
        ctx.abort()


if __name__ == '__main__':
  main()

