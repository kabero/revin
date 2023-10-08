import datetime
import os
import re
import subprocess
import shutil
import uuid
from collections import defaultdict


REMINDER_CMD = '/opt/homebrew/bin/reminders'
EDITOR_CMD = '/opt/homebrew/bin/nvim'
TMP_DIR = 'tmp/'
BACKUP_DIR = 'backup/'


class App():
    def __init__(self):
        self.reminder = Reminder()
        self.reminder.change_list('Inbox')
        self.last_tmp_file = None

    def edit_reminder(self):
        self._create_tmp_file_for_editing_reminder()
        self.backup()
        old_tasks = self._csv2hash()

        self._open_file_with_editor(self.last_tmp_file)
        new_tasks = self._csv2hash()
        adding_keys, deleting_keys, updating_keys = self._diff(old_tasks, new_tasks)

        if not updating_keys and not adding_keys and not deleting_keys:
            print("Nothing to do.\n")
            return

        msg = "Confirm:\n"
        if adding_keys:
            msg += "  " + '\n  '.join([f"Add \"{new_tasks[key]}\"" for key in adding_keys]) + '\n'
        if updating_keys:
            msg += "  " + '\n  '.join([f"Update \"{old_tasks[key]}\" -> \"{new_tasks[key]}\"" for key in updating_keys]) + '\n'
        if deleting_keys:
            msg += "  " + '\n  '.join([f"Delete \"{old_tasks[key]}\"" for key in deleting_keys]) + '\n'
        msg += 'Answer(y/n): '

        if self._confirm(msg):
            # If we don't run delete last, IDs might become inconsistent
            if updating_keys:
                self._update_tasks(updating_keys, new_tasks)
            if adding_keys:
                self._add_tasks(adding_keys, new_tasks)
            if deleting_keys:
                self._delete_tasks(deleting_keys)

        self._delete_tmp_file()

    def undo(self):
        # TODO: Not implemented
        pass

    def redo(self):
        # TODO: Not implemented
        pass

    def backup(self):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        today = datetime.datetime.today()
        file_name = f"{today.strftime('%Y-%m-%d-%H%M%S')}.csv"
        shutil.copyfile(self.last_tmp_file, os.path.join(BACKUP_DIR, file_name))

    def _confirm(self, message):
        while True:
            user_input = input(message).lower().strip()
            confirmed = False
            match user_input:
                case "y" | "ye" | "yes":
                    confirmed = True
                    break
                case "n" | "no":
                    confirmed = False
                    break
                case _:
                    continue
            print("\n")
        return confirmed

    def _csv2hash(self):
        tasks = defaultdict()
        with open(self.last_tmp_file, 'r') as f:
            lines = f.readlines()

        dummy_id = 999999
        for line in lines:
            tmp = line.split('\t', maxsplit=2)
            if len(tmp) == 0:
                continue
            elif len(tmp) == 1:
                dummy_id += 1
                id, content = dummy_id, tmp[0].strip()
            else:
                id, content = tmp[0], tmp[1].strip()
            tasks[id] = content

        return tasks

    def _add_tasks(self, keys, tasks):
        for key in keys:
            self.reminder.add(tasks[key])

    def _delete_tasks(self, keys):
        for key in keys[::-1]:
            self.reminder.delete(key)

    def _update_tasks(self, keys, tasks):
        for key in keys:
            self.reminder.update(key, tasks[key])

    def _diff(self, old, new):
        keys_intersection = set(old.keys()) & set(new.keys())

        deleting_keys = list(old.keys() - keys_intersection)
        adding_keys = list(new.keys() - keys_intersection)

        updating_keys = []
        for key in keys_intersection:
            if (old[key] != new[key]):
                updating_keys.append(key)

        adding_keys = sorted(list(adding_keys))
        deleting_keys = sorted(list(deleting_keys))
        updating_keys = sorted(list(updating_keys))

        return adding_keys, deleting_keys, updating_keys

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
        res = subprocess.run(command, **opts).stdout.strip()
        return res

    def get_all_tasks(self):
        command = [REMINDER_CMD, 'show', self.current_list]
        opts = {"capture_output": True, "check": True, "text": True}
        res = subprocess.run(command, **opts).stdout.strip()

        res = res.split('\n')
        buff = res[0]
        for line in res[1:]:
            if re.match(r'^\d+: ', line):
                buff += '\n'
            buff += line
        return buff

    def update(self, task_id, content):
        command = [REMINDER_CMD, 'edit', self.current_list, task_id, content]
        subprocess.run(command)

    def add(self, content):
        command = [REMINDER_CMD, 'add', self.current_list, content]
        subprocess.run(command)

    def delete(self, task_id):
        command = [REMINDER_CMD, 'delete', self.current_list, task_id]
        subprocess.run(command)

    def complete(self, task_id):
        command = [REMINDER_CMD, 'complete', self.current_list, task_id]
        subprocess.run(command)

    def uncomplete(self, task_id):
        command = [REMINDER_CMD, 'uncomplete', self.current_list, task_id]
        subprocess.run(command)


def revin():
    app = App()
    app.edit_reminder()


def main():
    app = App()
    app.edit_reminder()


if __name__ == "__main__":
    main()
