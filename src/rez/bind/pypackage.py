"""
Binds a python package as a rez package.
"""
from __future__ import absolute_import

import os
import sys

try:
     import xmlrpclib
except ImportError:
     import xmlrpc.client as xmlrpclib

from rez.bind._utils import check_version, make_dirs
from rez.package_maker__ import make_package
from rez.utils.platform_ import platform_
from rez.vendor.version.version import Version
import imp
import setuptools
import urllib2
import tarfile
import zipfile
import shutil
import re
import subprocess
import distutils.core


SETUPTOOLS_ARGS = None


def setup_parser(parser):
    parser.add_argument("--pypkg", type=str, metavar="PYPKG", required=True,
                        help="The python package to bind")
    parser.add_argument("--name", type=str, metavar="NAME", required=False, default=None,
                        help="The name of the package to be created")
    parser.add_argument("--version", type=str, required=False,
                        help="The version of the python package to bind")


def commands():
    env.PATH.append('{this.root}/bin')
    env.PYTHONPATH.append('{this.root}/python')


def bind(path, version_range=None, opts=None, parser=None):
    if opts and opts.pypkg:
        py_package_name = opts.pypkg
        if opts.name:
            package_name = opts.name
        else:
            package_name = py_package_name.replace('-', '_')
    else:
        raise ValueError('A package name needs to be specified')

    # connect to PyPi and get the released package versions
    pypi_client = xmlrpclib.ServerProxy('https://pypi.python.org/pypi')
    package_versions = sorted(pypi_client.package_releases(py_package_name), key=lambda v: Version(v))
    if len(package_versions) < 1:
        raise ValueError('Invalid package name: {}'.format(package_name))

    # get the version
    if opts.version:
        version = next((v for v in package_versions if v == opts.version), None)
        if version is None:
            raise ValueError('Invalid version: {}, valid versions: {}'.format(opts.version, package_versions))
    else:
        version = package_versions[-1]

    check_version(Version(version), version_range)

    # get the source distribution, this could be better and try to install wheels as well
    release_info = next(
        (r for r in pypi_client.release_urls(py_package_name, version) if r['packagetype'] == 'sdist'),
        None
    )

    if release_info is None:
        raise ValueError(
            'No source distribution (we don\'t support wheels at the moment) for {} {}'.format(py_package_name, version)
        )

    # clear the temp dir if it exists
    tmp_dir = os.path.join(platform_.tmpdir, package_name)
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)
    os.mkdir(tmp_dir)

    # download file to tmp dir
    handle = urllib2.urlopen(release_info['url'])
    src_archive = os.path.join(tmp_dir, release_info['filename'])
    with open(src_archive, 'wb') as src_archive_fp:
        src_archive_fp.write(handle.read())

    # decompress the file
    package_dir = None
    if release_info['filename'].endswith('.zip'):
        zfile = zipfile.ZipFile(src_archive, 'r')
        zfile.extractall(tmp_dir)
        package_dir = src_archive.replace('.zip', '')
    elif release_info['filename'].endswith('.tar.gz'):
        tfile = tarfile.open(src_archive, 'r:gz')
        tfile.extractall(tmp_dir)
        package_dir = src_archive.replace('.tar.gz', '')
    elif release_info['filename'].endswith('.tgz'):
        tfile = tarfile.open(src_archive, 'r:gz')
        tfile.extractall(tmp_dir)
        package_dir = src_archive.replace('.tgz', '')
    else:
        raise ValueError('Package file downloaded cannot be decompressed: {}'.format(src_archive))

    setup_file = os.path.join(package_dir, 'setup.py')

    if not os.path.exists(setup_file):
        raise RuntimeError(
            'Package does not contain a "setup.py" file in the root of the archive: {}'.format(py_package_name)
        )

    def setup_dummy(*args, **kwargs):
        global SETUPTOOLS_ARGS
        SETUPTOOLS_ARGS = {}

        if 'scripts' in kwargs:
            SETUPTOOLS_ARGS['scripts'] = kwargs['scripts']

        if 'description' in kwargs:
            SETUPTOOLS_ARGS['description'] = kwargs['description']

        if 'long_description' in kwargs:
            SETUPTOOLS_ARGS['long_description'] = kwargs['long_description']

        if 'author' in kwargs:
            SETUPTOOLS_ARGS['author'] = kwargs['author']

        if 'author_email' in kwargs:
            SETUPTOOLS_ARGS['author_email'] = kwargs['author_email']

        if 'install_requires' in kwargs:
            SETUPTOOLS_ARGS['install_requires'] = kwargs['install_requires']

        if 'setup_requires' in kwargs:
            SETUPTOOLS_ARGS['setup_requires'] = kwargs['setup_requires']

        if 'version' in kwargs:
            SETUPTOOLS_ARGS['version'] = kwargs['version']
        else:
            raise RuntimeError('A package must have a version.')

    # duck type the setup function so we can steal the arguments passed to it
    setuptools.setup = setup_dummy
    distutils.core.setup = setup_dummy

    cwd = os.getcwd()
    os.chdir(package_dir)
    sys.path.extend([package_dir])
    old_args = sys.argv[:]
    try:
        _ = imp.load_source('{}_setup'.format(package_name), setup_file)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e
    sys.argv = old_args[:]
    os.chdir(cwd)
    sys.path.remove(package_dir)

    def parse_setup_requirements(req_str):
        '''
        e.g. "arrow >= 0.4.4, < 1" -> 'arrow-0.4.4+<1
        :param req_str: requirement in the setuptools format
        :return: requirement in the rez format
        '''
        req_str = req_str.replace('-', '_')

        if not any((op in req_str for op in ['<', '>', '='])):
            # even simpler "arrow" req
            return req_str.strip()
        if '==' in req_str:
            # just a simple "arrow == 0.4.4" req
            req_pgk_name, req_version = req_str.split('==')
            return '{}-{}'.format(req_pgk_name.strip(), req_version.strip())

        req_space_split = req_str.split(' ')
        req_pgk_name = req_space_split[0]
        req_pgk_req_str = ' '.join(req_space_split[1:])
        requirements = map(lambda s: s.strip(), req_pgk_req_str.split(','))

        versions_rewrite = []
        for sub_requirement_str in requirements:
            sub_requirement_match = re.match(r'([<>=]+?) ?([0-9a-zA-Z\.]+)', sub_requirement_str)
            operation = sub_requirement_match.group(1).strip()
            req_version = sub_requirement_match.group(2).strip()
            if operation == '>=':
                versions_rewrite.insert(0, '{}+'.format(req_version))
            elif operation == '<':
                versions_rewrite.append('<{}'.format(req_version))
            else:
                raise RuntimeError('Unable to translate operation: "{}" in requirement: {}'.format(operation, req_str))
        return '{}-{}'.format(req_pgk_name, ''.join(versions_rewrite))

    def make_root(variant, root):
        binpath = make_dirs(root, "bin")
        pythonpath = make_dirs(root, "python")
        headerpath = make_dirs(root, "include")
        install_cmd = ' '.join([
            'pip', 'install',
            '--no-deps', '--ignore-installed', '--verbose', '--verbose', '--verbose',
            '--global-option="--verbose"',
            '--install-option="--install-headers={}"'.format(headerpath),
            '--install-option="--install-purelib={}"'.format(pythonpath),
            '--install-option="--install-platlib={}"'.format(pythonpath),
            '--install-option="--install-scripts={}"'.format(binpath),
            py_package_name
        ])
        try:
            subprocess.check_output(
                install_cmd,
                cwd=package_dir
            )
        except subprocess.CalledProcessError as _:
            raise RuntimeError('Bind failed to install python package with command: {}'.format(install_cmd))

    with make_package(package_name, path, make_root=make_root) as pkg:
        pkg.version = version
        if 'description' in SETUPTOOLS_ARGS:
            if len(SETUPTOOLS_ARGS['description']) < 150:
                pkg.nice_name = SETUPTOOLS_ARGS['description']
            else:
                pkg.nice_name = SETUPTOOLS_ARGS['description'][:147] + '...'

        if 'long_description' in SETUPTOOLS_ARGS:
            pkg.description = SETUPTOOLS_ARGS['long_description']

        author_parts = []
        if 'author' in SETUPTOOLS_ARGS:
            author_parts.append(SETUPTOOLS_ARGS['author'])
        if 'author_email' in SETUPTOOLS_ARGS:
            author_parts.append(SETUPTOOLS_ARGS['author_email'])
        if len(author_parts) > 0:
            pkg.authors = [' '.join(author_parts)]
        else:
            pkg.authors = []

        if 'install_requires' in SETUPTOOLS_ARGS:
            pkg.requires = [parse_setup_requirements(req) for req in SETUPTOOLS_ARGS['install_requires']]
        else:
            pkg.requires = []

        if 'setup_requires' in SETUPTOOLS_ARGS:
            pkg.build_requires = [parse_setup_requirements(req) for req in SETUPTOOLS_ARGS['setup_requires']]

        if 'scripts' in SETUPTOOLS_ARGS:
            pkg.tools = [os.path.split(script)[-1] for script in SETUPTOOLS_ARGS['scripts']]
        pkg.commands = commands

    return package_name, Version(version)
