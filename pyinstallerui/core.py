import os
import platform
import re
import sys
from itertools import chain
from pathlib import Path
from subprocess import PIPE, Popen, list2cmdline
from urllib.request import urlopen

import questionary

from . import __version__

CURRENT_PYTHON_PATH = sys.executable
IS_WIN = 'Windows' in platform.platform()
CWD = os.getcwd()
PYINSTALLER_KWARGS = {
    '--noconfirm': {
        'checked': True,
        'type': bool,
        'msg': 'Where to put all the temporary work files. (default: ./build)',
    },
    '--onefile': {
        'type': bool,
        'msg': 'Create a one-file bundled executable.',
    },
    '--icon': {
        'type': str,
        'msg': 'FILE.ico or FILE.exe,ID or FILE.icns.',
    },
    '--windowed': {
        'type': bool,
        'msg': 'Run without console.',
    },
    '--distpath': {
        'type': str,
        'msg': 'Where to put the bundled app (default: ./dist).',
    },
    '--key': {
        'type': str,
        'msg': 'The key used to encrypt Python bytecode',
    },
    '--paths': {
        'type': str,
        'msg': 'A path to search for imports (like PYTHONPATH). separated by ‘:’',
    },
    '--add-data': {
        'type': str,
        'msg': 'Additional non-binary files or folders to be added to the executable',
    },
    '--add-binary': {
        'type': str,
        'msg': 'Additional binary files to be added to the executable',
    },
    '--upx-dir': {
        'type': str,
        'msg': 'Path to UPX utility (default: search the execution path)',
    },
    '--ascii': {
        'type': bool,
        'msg': 'Do not include unicode encoding support (default: included if available)',
    },
    '--clean': {
        'type': bool,
        'msg': 'Clean PyInstaller cache and remove temporary files before building.',
    },
    '--log-level': {
        'type': str,
        'msg': 'Amount of detail in build-time console messages',
    },
    '[Custom]': {
        'type': str,
        'msg': 'Input some custom args of pyinstaller',
    },
}


def clean_folder(path):
    for sub in path.iterdir():
        if sub.is_dir():
            delete_folder(sub)
        else:
            sub.unlink()


def delete_folder(path):
    clean_folder(path)
    path.rmdir()


def strip_quote(path):
    # return re.sub(r'^\s*[\'"](.*?)[\'"]\s*$', r'\1', path)
    return re.sub(r'(^[\'"\s]+|[\'"\s]+$)', r'', path)


def run(args, timeout=60, print_output=True, **kwargs):
    proc = Popen(args=args, stdout=PIPE, stderr=PIPE, **kwargs)
    output = []
    for line in chain(proc.stdout, proc.stderr):
        line = line.decode().strip()
        output.append(line)
        if print_output:
            print(line, flush=1)
    return '\n'.join(output)


class Venvs(object):
    GLOBAL_VENV_PATH = Path.home() / '.temp_venvs'
    CREATE_VENV_ARGS = [CURRENT_PYTHON_PATH, '-m', 'venv']

    def __init__(self):
        if not self.GLOBAL_VENV_PATH.is_dir():
            self.GLOBAL_VENV_PATH.mkdir()

    @classmethod
    def list_venvs(cls):
        return [i.name for i in cls.GLOBAL_VENV_PATH.iterdir() if i.is_dir()]

    @classmethod
    def rm_venv(cls, name):
        path = cls.GLOBAL_VENV_PATH / name
        if path.is_dir():
            delete_folder(path)


class Venv(object):
    pip_action_choices = [
        'No action', 'Install', 'Uninstall', 'List',
        'Custom(input raw `pip` command)'
    ]

    def __init__(self, name=None):
        self.name = name
        if name:
            self.venv_path = Venvs.GLOBAL_VENV_PATH / name
        else:
            self.venv_path = Venvs.GLOBAL_VENV_PATH / 'tmp'
            if not self.venv_path.is_dir():
                self.venv_path.mkdir()

    @property
    def bin_path(self):
        return self.get_bin_path()

    @property
    def python_path(self):
        return self.get_python_path()

    @property
    def python_path_str(self):
        return str(self.python_path)

    @property
    def pip_path(self):
        return self.bin_path / 'pip'

    @property
    def pyinstaller_path(self):
        return self.bin_path / 'pyinstaller'

    def get_bin_path(self):
        if IS_WIN:
            return self.venv_path / 'Scripts'
        else:
            return self.venv_path / 'bin'

    def get_python_path(self, bin_path=None):
        if not self.name:
            return Path(CURRENT_PYTHON_PATH)
        bin_path = bin_path or self.get_bin_path()
        if IS_WIN:
            return bin_path / 'python.exe'
        else:
            return bin_path / 'python'

    @classmethod
    def create_venv(cls, name):
        if cls.is_valid_name(name):
            print(f'Creating venv at {Venvs.GLOBAL_VENV_PATH}...')
            run(Venvs.CREATE_VENV_ARGS + [name], cwd=Venvs.GLOBAL_VENV_PATH)
            print(f'Venv {name} Created.')
        else:
            print(
                f'[Error] Venv name should not contain space, but "{name}" given.'
            )
        return cls(name)

    @classmethod
    def is_valid_name(cls, name):
        if re.search(r'\s', name):
            return False
        else:
            return True

    def is_valid(self):
        return self.is_valid_name(self.name) and self.python_path.is_file()

    def ensure_pip(self):
        output = run([self.python_path_str, '-m', 'pip', '-V'])
        if not output.startswith('pip'):
            url = 'https://bootstrap.pypa.io/get-pip.py'
            print(f'Downloading and install `pip` from {url}')
            req = urlopen(url=url)
            content = req.read()
            with open(self.venv_path / 'get-pip.py', 'wb') as f:
                f.write(content)
            run([self.python_path_str, str(self.venv_path / 'get-pip.py')])
            (self.venv_path / 'get-pip.py').unlink()

    def check_pyinstaller(self):
        output = run([self.python_path_str, '-m', 'PyInstaller', '--version'],
                     print_output=False)
        return 'No module named' not in output

    def install_pyinstaller(self):
        run([self.python_path_str, '-m', 'pip', 'install', 'PyInstaller'],
            cwd=Venvs.GLOBAL_VENV_PATH)

    def pip_install(self, cmd, timeout=300):
        if not cmd.startswith('pip install '):
            print('pip command should startswith `pip install `')
            return
        cmd = f'{self.pip_path} {cmd[4:]}'
        os.system(cmd)

    def pip_uninstall(self, cmd, timeout=300):
        if not cmd.startswith('pip uninstall -y '):
            print('pip command should startswith `pip uninstall -y `')
            return
        cmd = f'{self.pip_path} {cmd[4:]}'
        os.system(cmd)

    def pip_list(self, timeout=300):
        cmd = f'{self.pip_path} list'
        os.system(cmd)

    def pip_custom(self, cmd, timeout=300):
        if not cmd.startswith('pip '):
            print('pip command should startswith `pip `')
            return
        cmd = f'{self.pip_path} {cmd[4:]}'
        os.system(cmd)

    def ask_if_install_pyinstaller(self):
        need_install = questionary.confirm(
            '`PyInstaller` not found, do you want to install it?',
            default=True).ask()
        if need_install:
            self.install_pyinstaller()

    def run(self, script_path, temp_cwd=None):
        if temp_cwd:
            os.chdir(temp_cwd)
        cmd = f'{self.python_path} "{script_path}"'
        os.system(cmd)
        if temp_cwd:
            os.chdir(CWD)


def prepare_venv():
    venv = None
    venvs = Venvs()
    new_venv = '[Create New Venv]'
    rm_venv = '[Remove Venv]'
    exit_choice = '[Exit]'
    print(f'[Venv path]: {venvs.GLOBAL_VENV_PATH}\n{"-" * 40}')
    while 1:
        choices = [new_venv, rm_venv, exit_choice] + venvs.list_venvs()
        name = questionary.select(
            'Choose a venv by name, or create a new one:',
            choices=choices).ask()
        if name == exit_choice:
            break
        elif name == rm_venv:
            while 1:
                name = questionary.select(
                    'Choose a name to remove:',
                    choices=['[Exit]'] + venvs.list_venvs()).ask()
                if name == '[Exit]':
                    break
                print('Venv Removing...')
                venvs.rm_venv(name)
                print('Venv Removed.')
            continue
        else:
            if name == new_venv:
                venvs.rm_venv(name)
                name = input('Input the venv name:\n').strip()
                if not name:
                    print(f'Name can not be null.')
                    continue
                venv = Venv.create_venv(name)
            else:
                venv = Venv(name)
        if not venv.is_valid():
            print(f'Bad venv ({name}), please retry again.')
            continue
        print(f'Prepare venv ({venv.name}) success.')
        break
    return venv


def prepare_pip(venv):
    venv.ensure_pip()
    if not venv.check_pyinstaller():
        venv.ask_if_install_pyinstaller()
    while 1:
        action = questionary.select(
            'Choose action of `pip`:', choices=venv.pip_action_choices).ask()
        index = venv.pip_action_choices.index(action)
        if index == 0:
            break
        elif index == 1:
            while 1:
                cmd = questionary.text(
                    "Fill text for `pip install ` (null for exit):",
                    default='pip install ').ask()
                if cmd == 'pip install ':
                    break
                venv.pip_install(cmd=cmd)
        elif index == 2:
            while 1:
                cmd = questionary.text(
                    "Fill text for `pip uninstall -y ` (null for exit):",
                    default='pip uninstall -y ').ask()
                if cmd == 'pip uninstall -y ':
                    break
                venv.pip_uninstall(cmd=cmd)
        elif index == 3:
            venv.pip_list()
        elif index == 4:
            while 1:
                cmd = questionary.text(
                    "Fill text for `pip ` (null for exit):",
                    default='pip ').ask()
                if cmd == 'pip ':
                    break
                venv.pip_custom(cmd=cmd)


def ask_script_cwd_path(venv, script_path, cwd):
    script_path = questionary.text(
        "Input python script path (null to Exit):",
        default=str(script_path)).ask().strip()
    if not script_path:
        return [None, None]
    script_path = strip_quote(script_path)
    script_path = Path(script_path)

    cwd = questionary.select(
        'Choose the cwd path:',
        choices=[str(CWD), str(script_path.parent), '[Custom CWD]']).ask()
    if cwd == '[Custom CWD]':
        cwd = questionary.text(
            "Input cwd path:", default=str(cwd)).ask().strip()
    cwd = strip_quote(cwd)
    cwd = Path(cwd)
    return script_path, cwd


def ask_for_args(venv, script_path, cwd, cache_path):
    cache_path_str = str(cache_path)
    args = [
        venv.python_path_str, '-m', 'PyInstaller',
        str(script_path), '--workpath', cache_path_str, '--specpath',
        cache_path_str
    ]
    # app name
    appname = questionary.text(
        "App name (default to the script name):",
        default=re.sub(r'.pyw?$', '', script_path.name)).ask().strip()
    args.extend(['--name', appname])
    # check if want to set
    choices = []
    for key, value in PYINSTALLER_KWARGS.items():
        item = {
            'name': f'{key: <12} | {value["msg"]}',
            'checked': value.get('checked', False)
        }
        choices.append(item)
    tmp = questionary.checkbox(
        'Select the options to change:', choices=choices).ask()
    for choice in tmp:
        key = choice.split(' | ')[0].strip()
        item = PYINSTALLER_KWARGS[key]
        if item['type'] == bool:
            args.append(key)
        elif item['type'] == str:
            value = input(f'Input the {key} arg:\n{item["msg"]}\n').strip()
            if value:
                value = strip_quote(value)
                args.append(key)
                args.append(value)
        elif key == '[Custom]':
            while 1:
                value = input(
                    'Input the args one by one (null to exit):\n').strip()
                if not value:
                    break
                args.append(value)
    return args


def print_sep(size=40, sig='='):
    print(sig * size, flush=1)


def prepare_test_pyinstaller(venv):
    script_path, cwd = ['', '']
    while 1:
        script_path, cwd = ask_script_cwd_path(venv, script_path, cwd)
        if script_path is None:
            break
        if not (script_path.is_file() and (str(script_path).endswith('.py') or
                                           str(script_path).endswith('.pyw'))):
            print('[Error] script path should be a *.py or *.pyw file')
            continue
        if not cwd.is_dir():
            print('[Error] cwd path should be a dir')
            continue
        choice = questionary.select(
            'Choose a action for python script:',
            choices=['Test', 'Build', 'Exit']).ask()
        if choice == 'Exit':
            break
        elif choice == 'Test':
            print(f'Testing python script at {cwd}:')
            print_sep()
            # python xxx.py
            venv.run(script_path, cwd)
            print_sep()
        elif choice == 'Build':
            # pyinstaller xxx.py
            if not venv.check_pyinstaller():
                venv.ask_if_install_pyinstaller()
            cache_path = venv.venv_path / 'dist_cache'
            if not cache_path.is_dir():
                cache_path.mkdir()
            args = ask_for_args(venv, script_path, cwd, cache_path)
            print_sep()
            print(f'Building python script at {cwd}:\n{list2cmdline(args)}')
            run(args, cwd=cwd)
            clean = questionary.confirm(
                "Clean the cache files?", default=False).ask()
            if clean:
                clean_folder(cache_path)
        is_quit = questionary.confirm("Quit?", default=True).ask()
        if is_quit:
            if venv.name:
                is_del_venv = questionary.confirm(
                    f'Remove the `{venv.name}` venv?', default=False).ask()
                if is_del_venv:
                    Venvs.rm_venv(venv.name)
            quit()


def _main():
    print(f'{"=" * 40}\nPyinstaller UI v{__version__}\n{"=" * 40}')
    use_venv = questionary.confirm('Use venv?', default=False).ask()
    if use_venv:
        # Prepare for venv
        venv = prepare_venv()
        if not venv:
            return
        # Prepare for pip
        prepare_pip(venv)
    else:
        venv = Venv()
    # Prepare for PyInstaller / python test
    prepare_test_pyinstaller(venv)
    return venv


def main():
    try:
        _main()
    except KeyboardInterrupt:
        return


if __name__ == '__main__':
    main()
