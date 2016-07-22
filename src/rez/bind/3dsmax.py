"""
Binds a 3dsmax executable as a rez package.
"""
from __future__ import absolute_import

import os
import sys
import functools
from pkg_resources import resource_filename, Requirement

from rez.bind._utils import check_version, find_exe, extract_version, make_dirs
from rez.package_maker__ import make_package
from rez.system import system
from rez.utils.platform_ import platform_
from rez.vendor.version.version import Version


def setup_parser(parser):
    parser.add_argument("--root", type=str, metavar="PATH",
                        help="the folder in which 3dsmax was installed to.")


def win_commands(exepath):
    return '''env.PATH.append(r\'{0}\')

env.ADSK_3DSMAX_x64_2015 = r\'{0}\'
'''.format(exepath)


def bind(path, version_range=None, opts=None, parser=None):
    if platform_.name != 'windows':
        raise EnvironmentError('Only binds on windows at the moment')

    # find executable, determine version
    if opts and opts.root:
        bin_path = opts.root
    else:
        installed_versions = []
        autodesk_root = r'C:\Program Files\Autodesk'
        for app_folder in os.listdir(autodesk_root):
            if app_folder.startswith('3ds Max'):
                installed_versions.append(
                    (app_folder, Version(app_folder.replace('3ds Max', '').strip()))
                )
        if len(installed_versions) < 1:
            raise EnvironmentError(
                'Unable to find any installed version of 3ds Max under "{}"'.format(
                    autodesk_root
                )
            )

        app_folder, version = sorted(installed_versions, key=lambda v: v[1])[-1]

        bin_path = os.path.join(autodesk_root, app_folder)

    from win32api import GetFileVersionInfo, LOWORD, HIWORD
    try:
        info = GetFileVersionInfo(os.path.join(bin_path, '3dsmax.exe'), "\\")
        ms = info['FileVersionMS']
        ls = info['FileVersionLS']
        version = Version('{}.{}.{}.{}'.format(HIWORD(ms), LOWORD(ms), HIWORD(ls), LOWORD(ls)))
    except:
        raise EnvironmentError('Unknown version')

    check_version(version, version_range)

    def make_root(resources_path, variant, path):
        import shutil
        shutil.copy(
            os.path.join(resources_path, '3dsmax_icon.png'),
            os.path.join(path, '3dsmax_icon.png')
        )

    make_root_partial = functools.partial(make_root, resource_filename(Requirement.parse('rez'), "rez/bind/resources"))

    with make_package("3dsmax", path, make_root=make_root_partial) as pkg:
        pkg.version = version
        pkg.tools = ["3dsmax"]
        pkg.description = '3D DCC application'
        pkg.authors = ['Autodesk']
        pkg.requires = ['roaming_user']
        pkg.nice_name = '3DS Max'

        pkg.tools_info = {
            '3dsmax': {
                'command': ['start', '3DSMax', '/D', '%ADSK_3DSMAX_x64_2015%', '/wait', '/B', '3dsmax.exe'],
                'nice_name': '3ds Max',
                'priority': 89,
                'icon': '{root}/3dsmax_icon.png',
                'launch_in_prompt': False
            }
        }
        pkg.commands = win_commands(bin_path)
        pkg.variants = [system.variant]

    return "3dsmax", version
