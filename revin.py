# flake8: noqa E501
import datetime
import os
import re
import subprocess
import shutil
import uuid
from collections import OrderedDict


REMINDER_CMD = '/opt/homebrew/bin/reminders'
EDITOR_CMD = os.environ.get('EDITOR')
APP_HOME_DIR = os.path.expanduser("~/revin")
TMP_DIR = os.path.join(APP_HOME_DIR, 'tmp/')
BACKUP_DIR = os.path.join(APP_HOME_DIR, 'backup/')
MAX_REMINDER_SIZE = 100000000

BLACK = "\033[30m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
END = "\033[0m"


class InvalidFileError(Exception):
    pass


class InvalidOperationError(Exception):
    pass


class App():
    def __init__(self):
        self.reminder = Reminder()
        self.reminder.change_list('Inbox')
        self.last_tmp_file = ""
        self.max_id = MAX_REMINDER_SIZE - 1  # The maximum ID currently existing in the reminder
        os.makedirs(APP_HOME_DIR, exist_ok=True)
        os.makedirs(TMP_DIR, exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)

    def edit_reminder(self):
        self._create_tmp_file_for_editing_reminder()
        self.create_backup()
        old_tasks = self._csv2hash()
        self.max_id = len(old_tasks) - 1

        while True:
            self._open_file_with_editor(self.last_tmp_file)
            new_tasks = self._csv2hash()
            adding_keys, deleting_keys, updating_keys, completed_keys = self._diff(old_tasks, new_tasks)

            if not any([updating_keys, adding_keys, deleting_keys, completed_keys]):
                print("Nothing to do.\n")
                return

            msg = "Confirm:\n"
            msg += ''.join([f"  {GREEN}Add{END} \"{new_tasks[key]['content']}\"\n" for key in adding_keys[::-1]])
            msg += ''.join([f"  {BLUE}Update{END} \"{old_tasks[key]['content']}\" {BLUE}\n      ->{END} \"{new_tasks[key]['content']}\"\n" for key in updating_keys[::-1]])
            msg += ''.join([f"  {RED}Delete{END} \"{old_tasks[key]['content']}\"\n" for key in deleting_keys[::-1]])
            msg += ''.join([f"  {MAGENTA}Complete{END} \"{new_tasks[key]['content']}\"\n" for key in completed_keys[::-1]])
            msg += 'Answer(y/n/r): '

            confirmed, needs_reedit = self._confirm(msg)
            print("\n")
            if confirmed:
                # If we don't run delete and complete last, IDs might become inconsistent
                if adding_keys:
                    self._add_tasks(adding_keys, new_tasks)
                if updating_keys:
                    self._update_tasks(updating_keys, new_tasks)
                if deleting_keys or completed_keys:
                    self._delete_and_complete_tasks(deleting_keys, completed_keys)
                break
            elif needs_reedit:
                continue
            else:
                print("Aborted\n")
                break

        self._delete_tmp_file()

    def undo(self):
        # TODO: Not implemented
        pass

    def redo(self):
        # TODO: Not implemented
        pass

    def create_backup(self):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        today = datetime.datetime.today()
        file_name = f"{today.strftime('%Y-%m-%d-%H%M%S')}.csv"
        shutil.copyfile(
            self.last_tmp_file, os.path.join(BACKUP_DIR, file_name))

    def _confirm(self, message="Are you sure?(y/n/r)"):
        while True:
            user_input = input(message).lower().strip()
            match user_input:
                case "y" | "ye" | "yes":
                    confirmed = True
                    needs_reedit = False
                    break
                case "n" | "no":
                    confirmed = False
                    needs_reedit = False
                    break
                case "r" | "re" | "reedit":
                    confirmed = False
                    needs_reedit = True
                    break
                case _:
                    continue
            print("\n")
        return confirmed, needs_reedit

    def _csv2hash(self):
        tasks = {}
        with open(self.last_tmp_file, 'r') as f:
            lines = f.readlines()
        
        dummy_id = 999999
        for line in lines:
            is_completed = False
            tmp = line.split('\t', maxsplit=1)
            if len(tmp) == 0:
                continue
            elif len(tmp) == 1:
                dummy_id += 1
                id, content = str(dummy_id), tmp[0].strip()
            else:
                if re.fullmatch(r"\d+", tmp[0]):
                    id, content = tmp[0], tmp[1].strip()
                    if int(id) > self.max_id:
                        raise InvalidFileError("Do not include the ID when adding a task.")
                elif re.fullmatch(r"X\d+", tmp[0]):
                    id, content = tmp[0][1:], tmp[1].strip()
                    is_completed = True
                    if int(id) > self.max_id:
                        raise InvalidFileError("Do not include the ID when adding a task.")
                else:
                    dummy_id += 1
                    id, content = str(dummy_id), line

            if tasks.get(id):
                raise InvalidFileError("Duplicate Ids exist.")

            tasks[id] = {
                "content": content,
                "is_completed": is_completed
            }

        return tasks

    def _add_tasks(self, keys, tasks):
        for key in keys:
            self.reminder.add(tasks[key]["content"])

    def _update_tasks(self, keys, tasks):
        for key in keys:
            self.reminder.update(key, tasks[key]["content"])

    def _delete_and_complete_tasks(self, deleting_keys, completed_keys):
        # To avoid Id inconsistencies,
        # "complete" and "delete" must be processed in descending order of ID.
        d = OrderedDict()
        for key in deleting_keys:
            d[key] = 'delete'
        for key in completed_keys:
            d[key] = 'complete'
        sorted_d = OrderedDict(sorted(d.items(), key=lambda x: x[0], reverse=True))
        for key, operation in sorted_d.items():
            if operation == 'delete':
                self.reminder.delete(key)
            elif operation == 'complete':
                self.reminder.complete(key)
            else:
                raise InvalidOperationError(f"invalid operation {operation}\n")

    def _diff(self, old, new):
        keys_intersection = set(old.keys()) & set(new.keys())

        deleting_keys = list(old.keys() - keys_intersection)
        adding_keys = list(new.keys() - keys_intersection)

        updating_keys = []
        for key in keys_intersection:
            if (old[key]['content'] != new[key]['content']):
                updating_keys.append(key)
        completed_keys = {key: value for key, value in new.items() if value['is_completed']}

        adding_keys = sorted(list(adding_keys))
        deleting_keys = sorted(list(deleting_keys))
        updating_keys = sorted(list(updating_keys))
        completed_keys = sorted(list(completed_keys))

        return adding_keys, deleting_keys, updating_keys, completed_keys

    def _create_tmp_file_for_editing_reminder(self):
        os.makedirs(TMP_DIR, exist_ok=True)

        file_name = f'{uuid.uuid1()}.txt'
        file_path = os.path.join(TMP_DIR, file_name)
        content = self.reminder.get_all_tasks()
        content = self._convert_to_csv_format(content, delimiter="\t")
        with open(file_path, 'w') as f:
            f.write(content)
        self.last_tmp_file = file_path

    def _delete_tmp_file(self):
        os.remove(self.last_tmp_file)

    def _convert_to_csv_format(self, content, delimiter=', '):
        converted = ""
        for line in content.split('\n'):
            tmp = line.split(': ')
            converted += f"{tmp[0]}{delimiter}{tmp[1]}\n"
        return converted

    def _open_file_with_editor(self, file_name):
        command = [EDITOR_CMD, file_name]
        subprocess.run(command)


class Reminder():
    def __init__(self):
        self.current_list = ""

    def change_list(self, list_name):
        self.current_list = list_name

    def get_all_lists(self):
        command = [REMINDER_CMD, 'show-lists']
        opts = {"capture_output": True, "check": True, "text": True}
        output = subprocess.run(command, **opts).stdout.strip()
        return output

    def get_all_tasks(self):
        command = [REMINDER_CMD, 'show', self.current_list]
        opts = {"capture_output": True, "check": True, "text": True}
        output = subprocess.run(command, **opts).stdout.strip()

        output = output.split('\n')
        buff = output[0]
        for line in output[1:]:
            if re.match(r'^\d+: ', line):
                buff += '\n'
            buff += line
        return buff

    def update(self, task_id, content):
        command = [REMINDER_CMD, 'edit', self.current_list, task_id, content]
        subprocess.run(command, stdout=subprocess.DEVNULL)
        print(f"{BLUE}Updated{END} \"{content}\"")

    def add(self, content):
        command = [REMINDER_CMD, 'add', self.current_list, content]
        subprocess.run(command, stdout=subprocess.DEVNULL)
        print(f"{GREEN}Added{END} \"{content}\"")

    def delete(self, task_id):
        command = [REMINDER_CMD, 'delete', self.current_list, task_id]
        opts = {"capture_output": True, "check": True, "text": True}
        output = subprocess.run(command, **opts).stdout.strip()

        content = output.split(' ', maxsplit=1)[1][1:-1]
        print(f"{RED}Deleted{END} \"{content}\"")

    def complete(self, task_id):
        command = [REMINDER_CMD, 'complete', self.current_list, task_id]
        opts = {"capture_output": True, "check": True, "text": True}
        output = subprocess.run(command, **opts).stdout.strip()

        content = output.splitlines()[1].split(' ', maxsplit=1)[1][1:-1]
        print(f"{MAGENTA}Completed{END} \"{content}\"")

    def uncomplete(self, task_id):
        command = [REMINDER_CMD, 'uncomplete', self.current_list, task_id]
        opts = {"capture_output": True, "check": True, "text": True}
        output = subprocess.run(command, **opts).stdout.strip()

        content = output.split(' ', maxsplit=1)[1][1:-1]
        print(f"Uncompleted \"{content}\"")


def revin():
    app = App()
    app.edit_reminder()


def main():
    app = App()
    app.edit_reminder()


if __name__ == "__main__":
    main()
