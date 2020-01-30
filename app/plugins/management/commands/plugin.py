import os
import importlib
import textwrap
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            'plugin_command',
            type=str,
            nargs='+',
            default=[],
        )

    def handle(self, *args, **options):
        if options['plugin_command'][0] == 'list':
            print("---------------------------")
            print(" CORPORA PLUGIN COMMANDS")
            print("---------------------------\n")
            plugin_apps = [app for app in settings.INSTALLED_APPS if app.startswith('plugins.')]
            for plugin_app in plugin_apps:
                module_name = plugin_app.split('.')[1]
                if os.path.exists("{0}/plugins/{1}/commands.py".format(settings.BASE_DIR, module_name)):
                    command_module = importlib.import_module(plugin_app + '.commands')
                    for command_name, command_info in command_module.REGISTRY.items():
                        print("   -- {0}:{1}\n".format(module_name, command_name))
                        wrapper = textwrap.TextWrapper(initial_indent='      ', subsequent_indent='      ')
                        print(wrapper.fill(command_info['description']))
        else:
            command_error = True
            command_parts = options['plugin_command'][0].split(':')
            if len(command_parts) == 2:
                command_plugin = command_parts[0]
                command_name = command_parts[1]
                command_params = None

                if len(options['plugin_command']) > 1:
                    command_params = options['plugin_command'][1:]

                if os.path.exists("{0}/plugins/{1}/commands.py".format(settings.BASE_DIR, command_plugin)):
                    command_module = importlib.import_module("plugins.{0}.commands".format(command_plugin))
                    if command_name in command_module.REGISTRY:
                        command = getattr(command_module, command_name)
                        if command_params:
                            command(*command_params)
                        else:
                            command()
                        command_error = False

            if command_error:
                print("Please provide a valid plugin command formatted like [plugin]:[command]. To see a list of valid commands, run \"python3 manage.py plugin\"")