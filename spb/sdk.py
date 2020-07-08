# MIT License
# 
# Copyright (c) 2020 Superb AI Corporation.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import spb
import math
import time
import urllib


__author__ = spb.__author__
__version__ = spb.__version__

__all__ = ('Client', 'DataHandle')


class Client(object):
    def __init__(self, project_name=None):
        super().__init__()

        if project_name is None:
            print('[WARNING] Specify the name of a project to be accessed')
            print('Usage: client = Client(project_name=\"<your_project_name>\")')
            return

        self._project = Client._get_project(project_name)

    ##############################
    # Immutable variables
    ##############################

    def get_project_name(self):
        return self._project.name

    ##############################
    # Constructor
    ##############################

    @classmethod
    def _get_project(cls, project_name):
        command = spb.Command(type='describe_project')

        projects, num_of_projects = spb.run(command=command, option={'name': project_name}, page=1, page_size=1)

        if num_of_projects == 0:
            print('[WARNING] Project {} not found'.format(project_name))
            return None

        return projects[0]

    ##############################
    # Simple SDK functions
    ##############################

    def get_num_data(self):
        command = spb.Command(type='describe_label')
        option = {'project_id': self._project.id}
        _, num_data = spb.run(command=command, option=option, page=1, page_size=1)

        if num_data == 0:
            print('[WARNING] Data list is empty')

        return num_data

    def get_data(self, data_idx, num_data=None):
        if num_data is None:
            num_data = self.get_num_data()

        if data_idx >= num_data:
            print('[WARNING] Index out of bounds. None returned')
            return None

        command = spb.Command(type='describe_label')
        option = {'project_id': self._project.id}
        data, _ = spb.run(command=command, option=option, page=data_idx+1, page_size=1)
        return DataHandle(data[0], self._project)

    def get_data_page(self, page_idx, page_size=10, num_data=None):
        if num_data is None:
            num_data = self.get_num_data()

        num_pages = math.ceil(float(num_data) / page_size)
        if page_idx >= num_pages:
            print('[WARNING] Index out of bounds. Empty list returned')
            return []

        command = spb.Command(type='describe_label')
        option = {'project_id': self._project.id}
        data_page, _ = spb.run(command=command, option=option, page=page_idx+1, page_size=page_size)
        for data in data_page:
            yield DataHandle(data, self._project)

    def get_data_all(self, page_size=10, num_data=None):
        if num_data is None:
            num_data = self.get_num_data()

        if num_data == 0:
            return []

        num_pages = math.ceil(float(num_data) / page_size)
        data_all = []
        for page_idx in range(num_pages):
            for data in self.get_data_page(page_idx, page_size, num_data):
                yield data


class DataHandle(object):
    _IMAGE_URL_LIFETIME_IN_SECONDS = 3600

    def __init__(self, data, project):
        super().__init__()

        self._data = data
        self._project = project
        self._created = time.time()

    def _is_expired_image_url(self):
        global _IMAGE_URL_LIFETIME

        is_expired = time.time() - self._created > DataHandle._IMAGE_URL_LIFETIME_IN_SECONDS

        if is_expired:
            print('[WARNING] Image URL has been expired. Call get_data(...) of SuiteProject to renew URL')

        return is_expired

    def _upload_to_suite(self):
        command = spb.Command(type='update_label')
        _ = spb.run(command=command, option=self._data)

    ##############################
    # Immutable variables
    ##############################

    def get_key(self):
        return self._data.data_key

    def get_dataset_name(self):
        return self._data.dataset

    def get_status(self):
        return self._data.status

    def get_image_url(self):
        if self._is_expired_image_url():
            print('[WARNING] None returned')
            return None

        return self._data.data_url

    ##############################
    # Simple SDK functions
    ##############################

    def download_image(self, download_to=None):
        if self._is_expired_image_url():
            print('[WARNING] None returned')
            return None, None

        if download_to is None:
            download_to = self._data.data_key
            print('[WARNING] Downloaded to {}'.format(download_to))

        return urllib.request.urlretrieve(self._data.data_url, download_to)

    def get_numpy_image(self):
        try:
            import skimage.io
        except:
            print('[WARNING] Requires scikit-image library. None returned')
            return None

        if self._is_expired_image_url():
            print('[WARNING] None returned')
            return None

        return skimage.io.imread(self._data.data_url)

    def get_category_labels(self):
        category_map = self._project.label_interface['categorization']['word_map']
        id_to_name = {c['id']: c['name'] for c in category_map if c['id'] != 'root'}

        try:
            labels = [id_to_name[id] for id in self._data.result['categorization']['value']]
        except:
            # The given image does not have any image categorizations
            labels = []

        return labels

    def get_object_labels(self):
        try:
            labels = self._data.result['objects']
        except:
            # The given image does not have any object annotations
            labels = []

        return labels

    def set_category_labels(self, labels):
        category_map = self._project.label_interface['categorization']['word_map']
        name_to_id = {c['name']: c['id'] for c in category_map if c['id'] != 'root'}

        try:
            label_ids = [name_to_id[name] for name in labels]
        except KeyError:
            print('[WARNING] Invalid category name exists')
            return

        self._data.result = {**self._data.result, 'categorization': {'value': label_ids}}
        self._upload_to_suite()

    def set_object_labels(self, labels):
        self._data.result = {**self._data.result, 'objects': labels}
        self._upload_to_suite()
