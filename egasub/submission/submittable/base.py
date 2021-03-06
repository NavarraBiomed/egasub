import os
import re
import yaml
import time
from click import echo
from abc import ABCMeta, abstractmethod, abstractproperty

from egasub.exceptions import Md5sumFileError
from egasub.ega.entities import Sample, Attribute, \
                                File as EFile, \
                                Analysis as EAnalysis, \
                                Experiment as EExperiment
from egasub.ega.services.ftp import file_exists



def _get_md5sum(md5sum_file):
    try:
        checksum = open(md5sum_file, 'r').readline().rstrip()
    except:
        raise Md5sumFileError("Please make sure md5sum file '%s' exist" % md5sum_file)

    if not re.findall(r"^[a-fA-F\d]{32}$", checksum):
        raise Md5sumFileError("Please make sure md5sum file '%s' contain valid md5sum string" % md5sum_file)
    return checksum.lower()


class Submittable(object):
    __metaclass__ = ABCMeta

    @property
    def path(self):
        return self._path

    @property
    def submission_dir(self):
        return os.path.basename(self._path)

    @property
    def type(self):
        return self.__class__.__name__.lower()

    @property
    def metadata(self):
        return self._metadata

    @abstractproperty
    def status(self):
        return

    @property
    def local_validation_errors(self):
        return self._local_validation_errors
    
    @property
    def ftp_file_validation_errors(self):
        return self._ftp_file_validation_errors

    def _add_local_validation_error(self, type_, alias, field, message):
        self._local_validation_errors.append({
                "object_type" : type_,
                "object_alias": alias,
                "field": field,
                "error": message
            })
        
    def _add_ftp_file_validation_error(self,field,message):
        self._ftp_file_validation_errors.append({
                "field": field,
                "error": message
            })

    def _parse_meta(self):
        yaml_file = os.path.join(self.path, '.'.join([self.type, 'yaml']))
        try:
            with open(yaml_file, 'r') as yaml_stream:
                self._metadata = yaml.load(yaml_stream)

            # some basic validation of the YAML
            if self.type == 'experiment':
                if 'alias' in self._metadata.get('experiment', {}):
                    raise Exception("Can not have 'alias' for 'experiment' in %s." % yaml_file)
                if 'alias' in self._metadata.get('run', {}):
                    raise Exception("Can not have 'alias' for 'run' in %s." % yaml_file)
            if self.type == 'analysis':
                if 'alias' in self._metadata.get('analysis', {}):
                    raise Exception("Can not have 'alias' for 'analysis' in %s." % yaml_file)

        except Exception, e:
            raise Exception('Not a properly formed submission directory: %s' % self.submission_dir)

        self._parse_md5sum_file()


    def _parse_md5sum_file(self):
        """
        parse md5sum file(s) to get checksum and unencryptedChecksum
        """
        for f in self.metadata.get('files'):
            # sequence_file.paired_end.sample_y.fq.gz.gpg
            if not f.get('fileName'):
                # echo('Skip file entry without fileName specified.')  # for debug
                continue
            data_file_name = os.path.basename(f.get('fileName'))
            md5sum_file = os.path.join(self.path, data_file_name + '.md5')
            f['checksumMethod'] = 'md5'
            f['checksum'] = _get_md5sum(md5sum_file)
            f['checksum'] = _get_md5sum(md5sum_file)

            unencrypt_md5sum_file = os.path.join(self.path, re.sub(r'\.gpg$', '', data_file_name) + '.md5')
            f['unencryptedChecksum'] = _get_md5sum(unencrypt_md5sum_file)

    @abstractmethod
    def local_validate(self):
        pass
    
    @abstractmethod
    def ftp_files_remote_validate(self):
        pass

    def restore_latest_object_status(self, obj_type):
        if not obj_type in ('sample', 'analysis', 'experiment', 'run'):
            return

        obj = getattr(self, obj_type)

        status_file = os.path.join(self.path, '.status', '%s.log' % obj_type)

        try:
            with open(status_file, 'r') as f:
                lines = f.readlines()
                if lines:
                    line = lines[-1]
                    id_, alias, status, timestamp = line.split('\t')
                    if obj.alias and not obj.alias == alias:
                        pass # alias has changed, this should never happen, if it does, we simply ignore and do not restore the status
                    else:
                        obj.alias = alias
                        obj.status = status
        except:
            return

    def record_object_status(self, obj_type):
        if not obj_type in ('sample', 'analysis', 'experiment', 'run'):
            return

        status_dir = os.path.join(self.path, '.status')

        if not os.path.exists(status_dir):
            os.makedirs(status_dir)

        status_file = os.path.join(status_dir, '%s.log' % obj_type)

        obj = getattr(self, obj_type)

        with open(status_file, 'a') as f:
            f.write("%s\n" % '\t'.join([str(obj.id), str(obj.alias), str(obj.status), str(int(time.time()))]))

    def local_validate(self, ega_enums):
        # Alias validation
        if not self.sample.alias == self.submission_dir:
            self._add_local_validation_error("sample",self.sample.alias,"alias","Invalid value '%s'. Sample's alias must be set and match the submission directory name '%s'." % (self.sample.alias, self.submission_dir))

        # subjustId validation
        if not self.sample.subject_id:
            self._add_local_validation_error("sample",self.sample.alias,"subjectId","Invalid value, sample's subjectId must be set.")

        # Gender validation
        if not any(gender['tag'] == str(self.sample.gender_id) for gender in ega_enums.lookup("genders")):
            self._add_local_validation_error("sample",self.sample.alias,"gender","Invalid value '%s'" % self.sample.gender_id)

        # Case or control validation
        if not any(cc['tag'] == str(self.sample.case_or_control_id) for cc in ega_enums.lookup("case_control")):
            self._add_local_validation_error("sample",self.sample.alias,"caseOrControl","Invalid value '%s'" % self.sample.case_or_control_id)

        # phenotype validation
        if not self.sample.phenotype:
            self._add_local_validation_error("sample",self.sample.phenotype,"phenotype","Invalid value, sample's phenotype must be set.")


    def ftp_files_remote_validate(self,host,username, password):
        for _file in self._analysis.files:
            if not file_exists(host,username,password,_file.file_name):
                self._add_ftp_file_validation_error("fileName","File missing on FTP ega server: %s" % _file.file_name)


class Experiment(Submittable):
    @property
    def sample(self):
        return self._sample

    @property
    def experiment(self):
        return self._experiment

    @property
    def run(self):
        return self._run

    # Future todo: move these validations to a new Validator class
    def local_validate(self, ega_enums):
        super(Experiment, self).local_validate(ega_enums)

        # Instrument model validation
        if not any(model['tag'] == str(self.experiment.instrument_model_id) for model in ega_enums.lookup("instrument_models")):
            self._add_local_validation_error("experiment",self.experiment.alias,"instrumentModel","Invalid value '%s'" % self.experiment.instrument_model_id)

        # Library source validation
        if not any(source['tag'] == str(self.experiment.library_source_id) for source in ega_enums.lookup("library_sources")):
            self._add_local_validation_error("experiment",self.experiment.alias,"librarySources","Invalid value '%s'" % self.experiment.library_source_id)

        # Library selection validation
        if not any(selection['tag'] == str(self.experiment.library_selection_id) for selection in ega_enums.lookup("library_selections")):
            self._add_local_validation_error("experiment",self.experiment.alias,"librarySelection","Invalid value '%s'" % self.experiment.library_selection_id)

        # Library strategy validation
        if not any(strategy['tag'] == str(self.experiment.library_strategy_id) for strategy in ega_enums.lookup("library_strategies")):
            self._add_local_validation_error("experiment",self.experiment.alias,"libraryStrategies","Invalid value '%s'" % self.experiment.library_strategy_id)

        # Library layout validation
        if not any(layout['tag'] == str(self.experiment.library_layout_id) for layout in ega_enums.lookup("library_layouts")):
            self._add_local_validation_error("experiment",self.experiment.alias,"libraryLayoutId","Invalid value '%s'" % self.experiment.library_layout_id)

        # Run file type validation
        if not any(file_type['tag'] == str(self.run.run_file_type_id) for file_type in ega_enums.lookup("file_types")):
            self._add_local_validation_error("run",self.run.alias,"runFileTypeId","Invalid value '%s'" % self.run.run_file_type_id)


class Analysis(Submittable):
    def __init__(self, path):
        self._local_validation_errors = []
        self._ftp_file_validation_errors = []
        self._path = path

        try:
            self._parse_meta()

            self._sample = Sample.from_dict(self.metadata.get('sample'))
            self.restore_latest_object_status('sample')

            self._analysis = EAnalysis.from_dict(self.metadata.get('analysis'))
            self.restore_latest_object_status('analysis')

            self._analysis.files = map(lambda file_: EFile.from_dict(file_), self.metadata.get('files'))

            # not sure for what reason, EGA validation expect to have at least one attribute
            self._analysis.attributes = [
                Attribute('submitted_using', 'egasub')
            ]
        except Exception, err:
            raise Exception("Can not create 'alignment' submission from this directory: %s. Please verify it's content. Error: %s" % (self._path, err))


    @property
    def status(self):
        if self.analysis.status:
            return self.analysis.status
        else:
            return 'NEW'  # hardcoded for now

    @property
    def type(self):
        return self.__class__.__bases__[0].__name__.lower()

    @property
    def files(self):
        return self._analysis.files

    @property
    def sample(self):
        return self._sample

    @property
    def analysis(self):
        return self._analysis

    def local_validate(self, ega_enums):
        super(Analysis, self).local_validate(ega_enums)
        # Reference genomes type validation
        if not any(cc['tag'] == str(self.analysis.genome_id) for cc in ega_enums.lookup("reference_genomes")):
            self._add_local_validation_error("analysis",self.analysis.alias,"referenceGenomes","Invalid value '%s'" % self.analysis.genome_id)

        # experimentTypeId type validation
        if not type(self.analysis.experiment_type_id) == list:
            self._add_local_validation_error("analysis",self.analysis.alias,"experimentTypes","Invalid value: experimentTypeId must be a list.")

        for e_type in self.analysis.experiment_type_id:
            if not any(cc['tag'] == str(e_type) for cc in ega_enums.lookup("experiment_types")):
                self._add_local_validation_error("analysis",self.analysis.alias,"experimentTypes","Invalid value '%s' in experimentTypeId" % e_type)

        # Chromosome references validation
        if not type(self.analysis.chromosome_references) == list:
            self._add_local_validation_error("analysis",self.analysis.alias,"chromosomeReferences","Invalid value: chromosomeReferences must be a list.")

        for chr_ref in self.analysis.chromosome_references:
            if not any(cc['tag'] == str(chr_ref.value) for cc in ega_enums.lookup("reference_chromosomes")):
                self._add_local_validation_error("analysis",self.analysis.alias,"chromosomeReferences","Invalid value '%s' in chromosomeReferences" % chr_ref.value)

