import os
import platform
import re
import sys
from itertools import chain
from pathlib import Path
from subprocess import PIPE, Popen, list2cmdline
from urllib.request import urlopen

from PyInquirer import prompt

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
    '--distpath': {
        'type': str,
        'msg': 'Where to put the bundled app (default: ./dist)',
    },
    '--icon': {
        'type': str,
        'msg': 'FILE.ico: apply that icon to an executable',
    },
    '--windowed': {
        'type': bool,
        'msg': 'Run without console.',
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

    def list_venvs(self):
        return [i.name for i in self.GLOBAL_VENV_PATH.iterdir() if i.is_dir()]

    def rm_venv(self, name):
        path = self.GLOBAL_VENV_PATH / name
        if path.is_dir():
            delete_folder(path)


class Venv(object):
    pip_action_choices = [
        'No action', 'Install', 'Uninstall', 'Custom(input raw `pip` command)'
    ]

    def __init__(self, name):
        self.name = name
        self.venv_path = Venvs.GLOBAL_VENV_PATH / name

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

    def pip_custom(self, cmd, timeout=300):
        if not cmd.startswith('pip '):
            print('pip command should startswith `pip `')
            return
        cmd = f'{self.pip_path} {cmd[4:]}'
        os.system(cmd)

    def ask_if_install_pyinstaller(self):
        need_install = prompt({
            'type': 'confirm',
            'name': 'name',
            'message': '`PyInstaller` not found, do you want to install it?',
            'default': True
        })['name']
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
    venvs = Venvs()
    new_venv = '[Create New Venv]'
    rm_venv = '[Remove Venv]'
    while 1:
        choices = [new_venv, rm_venv] + venvs.list_venvs()
        name = prompt({
            'type': 'list',
            'name': 'name',
            'message': 'Choose a venv by name, or create a new one:',
            'choices': choices
        })['name']
        if name == rm_venv:
            while 1:
                name = prompt({
                    'type': 'list',
                    'name': 'name',
                    'message': 'Choose a name to remove:',
                    'choices': ['Exit'] + venvs.list_venvs()
                })['name']
                if name == 'Exit':
                    break
                print('Venv Removing...')
                venvs.rm_venv(name)
                print('Venv Removed.')
            continue
        else:
            if name == new_venv:
                venvs.rm_venv(name)
                name = prompt({
                    'type': 'input',
                    'name': 'name',
                    'message': 'Input the venv name:',
                })['name'].strip()
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
        action = prompt({
            'type': 'list',
            'name': 'name',
            'message': 'Choose action of `pip`:',
            'choices': venv.pip_action_choices
        })['name']
        index = venv.pip_action_choices.index(action)
        if index == 0:
            break
        elif index == 1:
            while 1:
                cmd = prompt({
                    'type': 'input',
                    'name': 'name',
                    'message': 'Fill text for `pip install ` (null for exit):',
                    'default': 'pip install '
                })['name'].strip()
                if cmd == 'pip install ':
                    break
                venv.pip_install(cmd=cmd)
        elif index == 2:
            while 1:
                cmd = prompt({
                    'type': 'input',
                    'name': 'name',
                    'message': 'Fill text for `pip uninstall -y ` (null for exit):',
                    'default': 'pip uninstall -y '
                })['name'].strip()
                if cmd == 'pip uninstall -y ':
                    break
                venv.pip_uninstall(cmd=cmd)
        elif index == 3:
            while 1:
                cmd = prompt({
                    'type': 'input',
                    'name': 'name',
                    'message': 'Fill text for `pip ` (null for exit):',
                    'default': 'pip '
                })['name'].strip()
                if cmd == 'pip ':
                    break
                venv.pip_custom(cmd=cmd)


def ask_script_cwd_path(venv, script_path, cwd):
    script_path = prompt({
        'type': 'input',
        'name': 'name',
        'message': 'Input python script path (null to Exit):',
        'default': str(script_path),
    })['name'].strip()
    if not script_path:
        return [None, None]
    script_path = Path(script_path.strip())

    cwd = prompt({
        'type': 'list',
        'name': 'name',
        'message': 'Choose the cwd path:',
        'choices': [str(CWD), str(script_path.parent), '[Custom CWD]']
    })['name']
    if cwd == '[Custom CWD]':
        cwd = prompt({
            'type': 'input',
            'name': 'name',
            'message': 'Input cwd path:',
            'default': str(cwd),
        })['name'].strip()
    cwd = Path(cwd.strip())
    return script_path, cwd


def ask_for_args(venv, script_path, cwd, cache_path):
    cache_path_str = str(cache_path)
    args = [
        venv.python_path_str, '-m', 'PyInstaller',
        str(script_path), '--workpath', cache_path_str, '--specpath',
        cache_path_str
    ]
    # app name
    appname = prompt({
        'type': 'input',
        'name': 'name',
        'message': 'App name (default to the script name):',
        'default': re.sub(r'.pyw?$', '', script_path.name)
    })['name'].strip()
    args.extend(['--name', appname])
    # check if want to set
    choices = []
    for key, value in PYINSTALLER_KWARGS.items():
        item = {
            'name': f'{key: <12} | {value["msg"]}',
            'checked': value.get('checked', False)
        }
        choices.append(item)
    tmp = prompt({
        'type': 'checkbox',
        'message': 'Select the options to change:',
        'name': 'name',
        'choices': choices
    })['name']
    ajust_path = {'--distpath','--icon','--add-data','--add-binary','--upx-dir'}
    for choice in tmp:
        key = choice.split(' | ')[0].strip()
        item = PYINSTALLER_KWARGS[key]
        if item['type'] == bool:
            args.append(key)
        elif item['type'] == str:
            value = prompt({
                'type': 'input',
                'name': 'name',
                'message': f'Input the {key} arg:\n{item["msg"]}',
            })['name'].strip()
            if value:
                if key in ajust_path:
                    # update \ to /
                    value = Path(value).as_posix()
                args.append(key)
                args.append(value)
        elif key == '[Custom]':
            while 1:
                value = prompt({
                    'type': 'input',
                    'name': 'name',
                    'message': f'Input the args one by one, could not include `space` (null to exit):',
                })['name'].strip()
                if not value:
                    break
                args.append(value)
    return args


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
        choice = prompt({
            'type': 'list',
            'name': 'name',
            'message': 'Choose a action for python script:',
            'choices': ['Test', 'Build', 'Exit']
        })['name']
        if choice == 'Exit':
            break
        elif choice == 'Test':
            # python xxx.py
            venv.run(script_path, cwd)
        elif choice == 'Build':
            # pyinstaller xxx.py
            if not venv.check_pyinstaller():
                venv.ask_if_install_pyinstaller()
            cache_path = venv.venv_path / 'dist_cache'
            if not cache_path.is_dir():
                cache_path.mkdir()
            args = ask_for_args(venv, script_path, cwd, cache_path)
            print(f'Run python script at {cwd}:\n{list2cmdline(args)}')
            run(args, cwd=cwd)
            clean = prompt({
                'type': 'confirm',
                'message': 'Clean the cache files?',
                'name': 'name',
                'default': True,
            })['name']
            if clean:
                clean_folder(cache_path)


def main():
    # Prepare for venv
    venv = prepare_venv()
    # Prepare for pip
    prepare_pip(venv)
    # Prepare for PyInstaller / python test
    prepare_test_pyinstaller(venv)
    return venv


if __name__ == '__main__':
    main()