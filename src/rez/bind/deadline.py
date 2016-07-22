"""
Binds a 3dsmax executable as a rez package.
"""
from __future__ import absolute_import
from win32api import GetFileVersionInfo, LOWORD, HIWORD

import os
import sys
import functools
from pkg_resources import resource_filename, Requirement

from rez.bind._utils import check_version, find_exe, extract_version, make_dirs
from rez.package_maker__ import make_package
from rez.system import system
from rez.utils.platform_ import platform_
from rez.vendor.version.version import Version

PULSE_SERVERS = {
    "6": 'sbas04',
    "7": 'sbdeadline'
}


def setup_parser(parser):
    parser.add_argument("--root", type=str, metavar="PATH",
                        help="the folder in which Deadline was installed to.")


def win_commands(exepath, major_version):
    return '''env.PATH.append(r\'{0}\')
env.DEADLINE_PATH = r\'{0}\'
env.DEADLINE_PULSE = r\'{1}\''''.format(exepath, PULSE_SERVERS[str(major_version)])


def bind(path, version_range=None, opts=None, parser=None):
    if platform_.name != 'windows':
        raise EnvironmentError('Only binds on windows at the moment')

    # find executable, determine version
    if opts and opts.root:
        root_path = opts.root
        try:
            info = GetFileVersionInfo(os.path.join(root_path, 'bin', 'deadlinecommand.exe'), "\\")
            ms = info['FileVersionMS']
            ls = info['FileVersionLS']
            version = Version('{}.{}.{}.{}'.format(HIWORD(ms), LOWORD(ms), HIWORD(ls), LOWORD(ls)))
        except:
            raise EnvironmentError('Unknown version')
    else:
        installed_versions = []
        thinkbox_root = r'C:\Program Files\Thinkbox'
        app_folder_prefix = 'Deadline'
        for app_folder in os.listdir(thinkbox_root):
            if app_folder.startswith(app_folder_prefix):
                app_exe = os.path.join(thinkbox_root, app_folder, 'bin', 'deadlinecommand.exe')
                if os.path.exists(app_exe):
                    try:
                        info = GetFileVersionInfo(app_exe, "\\")
                        ms = info['FileVersionMS']
                        ls = info['FileVersionLS']
                        version = Version('{}.{}.{}.{}'.format(HIWORD(ms), LOWORD(ms), HIWORD(ls), LOWORD(ls)))
                    except:
                        raise EnvironmentError('Unknown version')
                    installed_versions.append(
                        (app_folder, version)
                    )

        if len(installed_versions) < 1:
            raise EnvironmentError(
                'Unable to find any installed version of Deadline under "{}"'.format(
                    thinkbox_root
                )
            )

        app_folder, version = sorted(installed_versions, key=lambda v: v[1])[-1]

        root_path = os.path.join(thinkbox_root, app_folder, 'bin')

    check_version(version, version_range)

    def make_root(resources_path, variant, path):
        import shutil
        shutil.copy(
            os.path.join(resources_path, 'deadline_monitor_icon.png'),
            os.path.join(path, 'deadline_monitor_icon.png')
        )

    make_root_partial = functools.partial(make_root, resource_filename(Requirement.parse('rez'), "rez/bind/resources"))

    with make_package("deadline", path, make_root=make_root_partial) as pkg:
        pkg.version = version
        pkg.tools = ["monitor"]
        pkg.description = 'Render Manager'
        pkg.authors = ['Thinkbox']
        pkg.requires = []
        pkg.nice_name = 'Deadline'

        pkg.tools_info = {
            'monitor': {
                'command': ['deadlinemonitor.exe'],
                'nice_name': 'Monitor',
                'priority': 89,
                'icon': '{root}/deadline_monitor_icon.png',
                'launch_in_prompt': False
            }
        }
        pkg.commands = win_commands(root_path, version.major)
        pkg.variants = [system.variant]

    return "deadline", version
