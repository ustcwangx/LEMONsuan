import os
import os.path as path
import json
import torch
import torch.utils.data as data
import numpy as np
import random
from PIL import Image
import pdb
import csv
import torchvision.transforms as transforms


def pil_loader(path):
	# open path as file to avoid ResourceWarning (https://github.com/python-pillow/Pillow/issues/835)
	with open(path, 'rb') as f:
		with Image.open(f) as img:
			return img.convert('RGB')


def accimage_loader(path):
	import accimage
	try:
		return accimage.Image(path)
	except IOError:
		# Potentially a decoding problem, fall back to PIL.Image
		return pil_loader(path)


def gray_loader(path):
	with open(path, 'rb') as f:
		with Image.open(f) as img:
			return img.convert('P')


def default_loader(path):
	from torchvision import get_image_backend
	if get_image_backend() == 'accimage':
		return accimage_loader(path)
	else:
		return pil_loader(path)


def find_classes(dir):
		classes = [d for d in os.listdir(dir) if os.path.isdir(os.path.join(dir, d))]
		classes.sort()
		class_to_idx = {classes[i]: i for i in range(len(classes))}

		return classes, class_to_idx


class Image_dataset(object):
    def __init__(self, data_dir='', mode = 'train', image_size = 84, transform = None,batch_size = 2,
                    episode_num = 10000, way_num = 5, shot_num = 5, query_num = 15,num_class = 64,loader=default_loader):
        super(Image_dataset, self).__init__()

        # set the paths of the csv files
        train_csv = os.path.join(data_dir, 'train.csv')
        val_csv = os.path.join(data_dir, 'val.csv')
        test_csv = os.path.join(data_dir, 'test.csv')

        data_list = []
        e = 0
        class_file = {'train':train_csv, 'val': val_csv, 'test':test_csv}
        # store all the classes and images into a dict
        class_img_dict = {}

        total_class_to_id = {}
        count = 0
        with open(class_file[mode]) as f_csv:
            f_temp = csv.reader(f_csv, delimiter=',')
            for row in f_temp:
                if f_temp.line_num == 1:
                    continue
                img_name, img_class = row

                if img_class in class_img_dict:
                    class_img_dict[img_class].append(img_name)
                else:
                    class_img_dict[img_class] = []
                    total_class_to_id[img_class] = count
                    count += 1
                    class_img_dict[img_class].append(img_name)
        f_csv.close()
        class_list = class_img_dict.keys()

        while e<episode_num:
            # construct each episode
            episode = []
            e += 1
            temp_list = random.sample(class_list, way_num)
            label_num = -1

            for item in temp_list:
                label_num += 1
                imgs_set = class_img_dict[item]
                support_imgs = random.sample(imgs_set, shot_num)
                query_imgs = [val for val in imgs_set if val not in support_imgs]

                if query_num < len(query_imgs):
                    query_imgs = random.sample(query_imgs, query_num)

                # the dir of support set
                query_dir = [path.join(data_dir, 'images', i) for i in query_imgs]
                support_dir = [path.join(data_dir, 'images', i) for i in support_imgs]
                # original_target = [total_class_to_id[item] for i in range(len(query_imgs))]
                if mode == 'train':
                    original_target = total_class_to_id[item]
                else:
                    original_target = -1
                # query_dir = [path.join(data_dir, os.path.join('image_final',i[1:3]), i) for i in query_imgs]
                # support_dir = [path.join(data_dir, os.path.join('image_final',i[1:3]), i) for i in support_imgs]

                data_files = {
                    "query_img": query_dir,
                    "support_set": support_dir,
                    "target": label_num,
                    "original_target": original_target
                }
                episode.append(data_files)
            data_list.append(episode)

        if mode == 'train':
            assert num_class == len(list(total_class_to_id.keys()))

        self.batch_size = batch_size
        self.data_list = data_list
        self.image_size = image_size
        self.transform = transform
        self.loader = loader
        self.gray_loader = gray_loader
        self.mode = mode

    def __len__(self):
        return len(self.data_list)

    def __getitem__(self, index):
        image_size = self.image_size
        episode_files = self.data_list[index]

        query_images = []
        query_targets = []
        support_images = []
        support_targets = []
        original_targets = []
        for i in range(len(episode_files)):
            data_files = episode_files[i]

            # load query images
            query_dir = data_files['query_img']

            for j in range(len(query_dir)):
                temp_img = self.loader(query_dir[j])

                # Normalization
                if self.transform is not None:
                    temp_img = self.transform(temp_img)
                query_images.append(temp_img.unsqueeze(0))

            # load support images
            # temp_support = []
            support_dir = data_files['support_set']
            for j in range(len(support_dir)):
                temp_img = self.loader(support_dir[j])

                # Normalization
                if self.transform is not None:
                    temp_img = self.transform(temp_img)
                support_images.append(temp_img.unsqueeze(0))

            # support_images.append(temp_support)

            # read the label
            target = data_files['target']
            original_target = data_files['original_target']

            query_targets.extend(np.tile(target, len(query_dir)))
            support_targets.extend(np.tile(target, len(support_dir)))
            original_targets.extend(np.tile(original_target,len(query_dir)))

        if self.mode == 'train':
            return torch.cat(support_images,dim=0),torch.cat(query_images,dim=0), \
               torch.tensor(support_targets),torch.tensor(query_targets),torch.tensor(original_targets)
        else:
            return torch.cat(support_images, dim=0), torch.cat(query_images, dim=0), \
            torch.tensor(support_targets), torch.tensor(query_targets)


# if __name__ == '__main__':
#
#     imageSize = 84
#     ImgTransform = transforms.Compose([
#         transforms.Resize((imageSize, imageSize)),
#         transforms.ToTensor(),
#         transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
#     ])
#     dataset = Image_dataset(data_dir= '/home/lemon/few-shot/DN4/dataset/miniImageNet/mini-imagenet', mode = 'train', image_size = 84,
#                             transform = ImgTransform,batch_size = imageSize,
#                     episode_num = 10000, way_num = 5, shot_num = 5, query_num = 10,num_class = 64,loader=default_loader)
#
#     train_dataloader = torch.utils.data.DataLoader(dataset,batch_size=4,num_workers=4,shuffle=False)
#
#     for batch_ix, (support_images,query_images,support_targets,query_targets,original_targets) in enumerate(train_dataloader):
#         print(support_images.shape)
#         print(query_images.shape)
#         print(support_targets.shape)
#         print(query_targets.shape)
#         print(original_targets.shape)
#         print(original_targets)
#         break