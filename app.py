#!/usr/bin/env python2.7
import json
import os
from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.plugins.callback import CallbackBase
from bottle import request, Bottle
from pexpect import pxssh, expect, spawn, fdpexpect, EOF
from time import sleep

PLAYBOOK_INSTALL_PATH = '/home/dzv/workflow/ansible/playbooks/ssh-redirector/ssh-redirector-install.yml'
PLAYBOOK_REMOVE_PATH = '/home/dzv/workflow/ansible/playbooks/ssh-redirector/ssh-redirector-remove.yml'
ANSIBLE_KEY = '/etc/secret/ansible/ansible_key'
BASE_DIR = '/home/dzv/workflow/ansible'
UNIT = '/etc/systemd/system/ssh-redirector.service'

class Halls(object):
    def __init__(self, id, ip, port, user, pswrd):
        self.id = id
        self.ip = ip
        self.port = port
        self.user = user
        self.pswrd = pswrd

    @property
    def PlayWithBook(self):

        playbook_path = PLAYBOOK_PATH
        ansible_key = ANSIBLE_KEY
        basedir=BASE_DIR

        Options = namedtuple('Options', {
            'verbosity',
            'forks',
            'become',
            'listhosts',
            'listtasks',
            'listtags',
            'syntax',
            'module_path',
            'connection',
            'remote_user',
            'sudo',
            'become_method',
            'become_user',
            'check',
            'private_key_file'
        })
        options = Options(verbosity=5,
                          forks=100,
                          become=True,
                          listhosts=False,
                          listtasks=False,
                          listtags=False,
                          syntax=False,
                          module_path=None,
                          connection='ssh',
                          remote_user=self.user,
                          sudo=True,
                          become_method='sudo',
                          become_user='root',
                          check=False,
                          private_key_file=ansible_key
                          )

        results_callback = ResultCallback()
        loader = DataLoader()
        variable_manager = VariableManager()

        inventory = Inventory(loader=loader,
                              variable_manager=variable_manager,
                              host_list=[self.ip]
                              )

        variable_manager.extra_vars = dict(host=self.ip,
                                           ansible_ssh_port=self.port,
                                           id=self.id,
                                           secret_root=basedir
                                           )
        variable_manager.set_inventory(inventory)

        passwords = {'become_pass' : self.pswrd}

        if not os.path.exists(playbook_path) or not os.path.exists(basedir) or not os.path.exists(ansible_key):
            print '[ERROR] The files or path not exist.'
            return 'Internal Server Error'

        pbex = PlaybookExecutor(playbooks=[playbook_path],
                                inventory=inventory,
                                variable_manager=variable_manager,
                                loader=loader,
                                options=options,
                                passwords=passwords)

        pbex._tqm._stdout_callback = results_callback
        result = pbex.run()

        results_raw = {'success': {self.ip : {"TASK" : {}}}, 'failed': {self.ip : {"TASK" : {}}}, 'unreachable': {self.ip : {"TASK" : {}}}}

        for task, result in results_callback.host_ok_result.items():
            results_raw['success'][self.ip]["TASK"][task] = result._result['changed']

        for task, result in results_callback.host_unreachable_result.items():
            results_raw['unreachable'][self.ip]["TASK"][task] = result._result['msg']

        for task, result in results_callback.host_failed_result.items():
            results_raw['failed'][self.ip]["TASK"][task] = result._result['msg']

        return json.dumps(results_raw, indent=4)

    def statusHalls(self):
        status = "systemctl status ssh-redirector"

        try:
            session = pxssh.pxssh()
            session.force_password = True
            session.login(self.ip, self.user, self.pswrd, port=self.port)
            session.sendline('systemctl show ssh-redirector --no-pager')
            session.prompt()
            result = session.before
            session.logout()
            for line in result:
                if "ActiveState=" in line:
                    state = line
                elif "Description=" in line:
                    hall = line

        except pxssh.ExceptionPxssh as e:
            return(e)
        finally:
            print state
            print hall


class ResultCallback(CallbackBase):
    def __init__(self, *args, **kwargs):
        super(ResultCallback, self).__init__(*args, **kwargs)
        self.host_ok_result = {}
        self.host_failed_result = {}
        self.host_unreachable_result = {}

    def playbook_on_task_start (self, name, is_conditional):
        if not name:
            name = 'gathering facts'
        self.task = name

    def v2_runner_on_unreachable(self, result):
        self.host_unreachable_result[self.task] = result

    def v2_runner_on_ok(self, result, *args, **kwargs):
        self.host_ok_result[self.task] = result

    def v2_runner_on_failed(self, result, *args, **kwargs):
        self.host_failed_result[self.task] = result


app = Bottle()

@app.post('/<halls:int>')
@app.get('/<halls:int>')
@app.delete('/<halls:int>')

def req_halls(halls):

    global PLAYBOOK_PATH
    halls=Halls(halls, request.query.ip, request.query.port, request.query.user, request.query.pswrd)

    if  request.method == "POST":
        PLAYBOOK_PATH=PLAYBOOK_INSTALL_PATH
        return halls.PlayWithBook

    elif request.method == "GET":
        return halls.statusHalls()

    elif request.method == "DELETE":
        PLAYBOOK_PATH = PLAYBOOK_REMOVE_PATH
        return halls.PlayWithBook

@app.error(404)
@app.error(405)
def error(error):
    return "Please do post/get/delete request in /halls?ip=?user=?pswrd="

app.run(host='localhost', port='8080', debug=False, quiet=False)

if __name__ == '__main__':
    main ()