#!/usr/bin/env python2.7
import json
import os
import sys
from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory, Host
from ansible.playbook import play
from ansible.errors import AnsibleFileNotFound, AnsibleParserError, AnsibleError
from ansible import utils
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase

from bottle import post, get, delete, request, run, route, template, error

PLAYBOOK_PATH = '/home/dzv/workflow/ansible/playbooks/ssh-redirector/ssh-redirector.yml'
ANSIBLE_KEY = '/etc/secret/ansible/ansible_key'
BASE_DIR = '/home/dzv/workflow/ansible'

class Halls(object):
    def __init__(self, id, ip, port, user, pswrd):
        self.id = id
        self.ip = ip
        self.port = port
        self.user = user
        self.pswrd = pswrd

    @property
    def setupHalls(self):

        playbook_path = PLAYBOOK_PATH
        ansible_key = ANSIBLE_KEY
        basedir=BASE_DIR

        Options = namedtuple('Options', [
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
                                     'remote_pass',
                                     'sudo_pass',
                                     'sudo',
                                     'become_method',
                                     'become_user',
                                     'check',
                                     'private_key_file',
                                     'basedir'
                                     ])
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
                          remote_pass=self.pswrd,
                          sudo_pass=self.pswrd,
                          sudo=True,
                          become_method='sudo',
                          become_user='root',
                          check=False,
                          private_key_file=ansible_key,
                          basedir=basedir
                          )

        loader = DataLoader()
        variable_manager = VariableManager()

        inventory = Inventory(loader=loader,
                              variable_manager=variable_manager,
                              host_list=[self.ip]
                              )

        variable_manager.extra_vars = dict(host=self.ip,
                                           ansible_ssh_port=self.port,
                                           id=self.id
                                           )
        variable_manager.set_inventory(inventory)

        passwords = {'ansible_ssh_pass' : self.pswrd,
                     'become_pass' : self.pswrd,
                     'sudo_pass' : self.pswrd,
                     'remote_pass' : self.pswrd,
                     'password' : self.pswrd}

        if not os.path.exists(playbook_path):
            print '[ERROR] The playbook does not exist.'
            return 'Internal Server Error'

        pbex = PlaybookExecutor(playbooks=[playbook_path],
                                inventory=inventory,
                                variable_manager=variable_manager,
                                loader=loader,
                                options=options,
                                passwords=passwords)
        results = pbex.run()
        return  results

    def statusHalls(self):
        pass

    def cleanupHalls(self):
        pass

@post('/<halls:int>')
@get('/<halls:int>')
@delete('/<halls:int>')
def req_halls(halls):
    halls=Halls(halls, request.query.ip, request.query.port, request.query.user, request.query.pswrd)
    if  request.method == "POST":
        return halls.setupHalls

    elif request.method == "GET":
        return "Show info " + str(halls.id)

    elif request.method == "DELETE":
        return "Delete " + str(halls.id)

@error(404)
@error(405)
def error(error):
    return "Please do post/get/delete request in /halls?ip=?user=?pswrd="

run(host='localhost', port=8080, debug=True)

