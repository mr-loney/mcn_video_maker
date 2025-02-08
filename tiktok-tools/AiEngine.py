import torchvision
import torch.nn as nn
from model.model import YOLOX, YOLOPAFPN, YOLOXHead

from torch.utils.data import Dataset
import cv2
import numpy as np
import torch
import os
from torch.utils.data import DataLoader
from model.model import MobileNetV3Small
import requests


class SlidePredictor(object):
    def __init__(self):
        torch.backends.cudnn.deterministic = True
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        self.checkpoint_path = os.path.join(cur_dir, "checkpoints/yolox_nano_416_slide_captcha_9k.pth")
        self.num_classes = 1
        self.conf_thre = 0.85
        self.test_size = (416, 416)
        self.device = "cpu"
        self.fp16 = False
        self.nms_thre = 0.65

        self.cls_names = (
            'captcha',
        )
        self.get_model()

    def get_model(self):
        def init_yolo(M):
            for m in M.modules():
                if isinstance(m, nn.BatchNorm2d):
                    m.eps = 1e-3
                    m.momentum = 0.03

        in_channels = [256, 512, 1024]
        backbone = YOLOPAFPN(0.33, 0.25, in_channels=in_channels, depthwise=True)
        head = YOLOXHead(self.num_classes, 0.25, in_channels=in_channels, depthwise=True)
        model = YOLOX(backbone, head)

        model.apply(init_yolo)
        model.head.initialize_biases(1e-2)
        ckpt = torch.load(self.checkpoint_path, map_location='cpu')
        model.load_state_dict(ckpt["model"])
        if self.device == 'gpu':
            model = model.cuda()
        model.eval()
        self.model = model

    def val_transform(self, img, res, input_size):
        img, _ = self.preproc(img, input_size, swap=(2, 0, 1))

        return img, np.zeros((1, 5))

    def preproc(self, img, input_size, swap=(2, 0, 1)):
        if len(img.shape) == 3:
            padded_img = np.ones((input_size[0], input_size[1], 3), dtype=np.uint8) * 114
        else:
            padded_img = np.ones(input_size, dtype=np.uint8) * 114

        r = min(input_size[0] / img.shape[0], input_size[1] / img.shape[1])
        resized_img = cv2.resize(
            img,
            (int(img.shape[1] * r), int(img.shape[0] * r)),
            interpolation=cv2.INTER_LINEAR,
        ).astype(np.uint8)
        padded_img[: int(img.shape[0] * r), : int(img.shape[1] * r)] = resized_img

        padded_img = padded_img.transpose(swap)
        padded_img = np.ascontiguousarray(padded_img, dtype=np.float32)
        return padded_img, r

    def postprocess(self, prediction, num_classes, conf_thre=0.7, nms_thre=0.45, class_agnostic=False):
        box_corner = prediction.new(prediction.shape)
        box_corner[:, :, 0] = prediction[:, :, 0] - prediction[:, :, 2] / 2
        box_corner[:, :, 1] = prediction[:, :, 1] - prediction[:, :, 3] / 2
        box_corner[:, :, 2] = prediction[:, :, 0] + prediction[:, :, 2] / 2
        box_corner[:, :, 3] = prediction[:, :, 1] + prediction[:, :, 3] / 2
        prediction[:, :, :4] = box_corner[:, :, :4]

        output = [None for _ in range(len(prediction))]
        for i, image_pred in enumerate(prediction):
            if not image_pred.size(0):
                continue

            class_conf, class_pred = torch.max(image_pred[:, 5: 5 + num_classes], 1, keepdim=True)

            conf_mask = (image_pred[:, 4] * class_conf.squeeze() >= conf_thre).squeeze()

            detections = torch.cat((image_pred[:, :5], class_conf, class_pred.float()), 1)
            detections = detections[conf_mask]
            if not detections.size(0):
                continue

            if class_agnostic:
                nms_out_index = torchvision.ops.nms(
                    detections[:, :4],
                    detections[:, 4] * detections[:, 5],
                    nms_thre,
                )
            else:
                nms_out_index = torchvision.ops.batched_nms(
                    detections[:, :4],
                    detections[:, 4] * detections[:, 5],
                    detections[:, 6],
                    nms_thre,
                )

            detections = detections[nms_out_index]
            if output[i] is None:
                output[i] = detections
            else:
                output[i] = torch.cat((output[i], detections))

        return output

    def get_image(self, image_url):
        try:
            if image_url.startswith('http'):
                resp = requests.get(image_url)
                image = np.asarray(bytearray(resp.content))
                image = cv2.imdecode(image, cv2.IMREAD_COLOR)
            else:
                image = cv2.imread(image_url, cv2.IMREAD_COLOR)
        except:
            image = None

        return image

    def inference(self, img):
        img_info = {"id": 0}
        if isinstance(img, str):
            img_info["file_name"] = os.path.basename(img)
            img = cv2.imread(img)
        else:
            img_info["file_name"] = None

        height, width = img.shape[:2]

        img_info["height"] = height
        img_info["width"] = width
        img_info["raw_img"] = img

        ratio = min(self.test_size[0] / img.shape[0], self.test_size[1] / img.shape[1])
        img_info["ratio"] = ratio

        img, _ = self.val_transform(img, None, self.test_size)
        img = torch.from_numpy(img).unsqueeze(0)
        img = img.float()
        if self.device == "gpu":
            img = img.cuda()
            if self.fp16:
                img = img.half()  # to FP16

        with torch.no_grad():
            outputs = self.model(img)
            outputs = self.postprocess(
                outputs, self.num_classes, self.conf_thre,
                self.nms_thre
            )
        return outputs, img_info

    def visual(self, output, img_info):
        ratio = img_info["ratio"]
        output = output.cpu()

        bboxes = output[:, 0:4]

        # preprocessing: resize
        bboxes /= ratio

        return bboxes[:, :4]

    def process(self, input_dict):
        # 输入大图的url地址
        file_name = input_dict["url1"]
        image = self.get_image(file_name)
        if image is not None:
            try:
                outputs, img_info = self.inference(image)
                if outputs is None or outputs[0] is None:
                    ret_code = -1
                    ret_msg = "Target Not Predicted"
                    res = None
                else:
                    bbox = self.visual(outputs[0], img_info)
                    res = {
                        "url1": input_dict["url1"],
                        "label_info": {
                            "bbox": bbox[0].numpy().tolist()
                        }
                    }
                    ret_code = 200
                    ret_msg = "OK"
            except Exception as e:
                print(e)
                ret_code = -1
                ret_msg = "Inner Error"
                res = None

            return ret_code, ret_msg, res

        else:
            ret_code = -1
            ret_msg = "Read Image Failed"
            res = None
            return ret_code, ret_msg, res


class CenterCrop(object):
    def __init__(self, crop_size):
        self.crop_size = crop_size

    def __call__(self, dct):
        imgs = dct["imgs"]
        height, width, _ = imgs.shape
        crop_w, crop_h = self.crop_size[0], self.crop_size[1]

        crop_y = int(round(height - crop_h) / 2.)
        crop_x = int(round(width - crop_w) / 2.)

        dct["imgs"] = imgs[crop_y:crop_y + crop_h, crop_x:crop_x + crop_w]

        return dct


class Normalize(object):
    def __init__(self, normalize=True, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]):
        self.NORM = normalize
        self.mean = mean
        self.std = std

    def __call__(self, dct):
        imgs = dct['imgs']

        if self.NORM:
            imgs = imgs / 255.

        for i in range(imgs.shape[-1]):
            imgs[:, :, i] = (imgs[:, :, i] - self.mean[i]) / self.std[i]

        dct['imgs'] = imgs
        return dct


class CaptchaMergedDataset(Dataset):
    def __init__(self, sub_img, img):
        super().__init__()
        self.samples = []

        angle_list = list(range(2, 178))
        angle_list.remove(90)

        for angle in angle_list:
            merged_img = self.merge_template(sub_img, img, angle)

            dct = {
                'imgs': merged_img,
                'angle': angle
            }
            self.samples.append(dct)

    def img_rotate(self, img, angle):
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated_img = cv2.warpAffine(img, M, (h, w))
        return rotated_img

    def merge_template(self, img, whirl_img, angle):
        img1 = self.img_rotate(img, -angle)
        size1 = 216
        img1 = cv2.resize(img1, (size1, size1))
        mask = np.zeros(img1.shape, dtype=np.uint8)
        center = (size1 // 2, size1 // 2)
        radius = 106
        cv2.circle(mask, center, radius, (255, 255, 255), -1)  # 取圆里面的内容
        image = cv2.bitwise_and(img1, mask)  # 取出圆的ROI

        img2 = self.img_rotate(whirl_img, angle)
        size2 = 346
        img2 = cv2.resize(img2, (size2, size2))

        image_pad = cv2.copyMakeBorder(image, 65, 65, 65, 65, cv2.BORDER_CONSTANT, value=(0, 0, 0))  # pad圆ROI到同样的大小
        img_save = np.zeros((size2, size2, 3), np.uint8)
        cv2.bitwise_or(img_save, img2, dst=img_save)

        mask_save = np.zeros(image_pad.shape, dtype=np.uint8)
        center = (size2 // 2, size2 // 2)
        radius = 106
        cv2.circle(mask_save, center, radius, (1, 2, 1), -1)  # 抠出待放圆ROI的区域
        where = np.where(mask_save == (1, 2, 1))

        img_save[where[1], where[0]] = (0, 0, 0)  # 把圆ROI贴回去
        cv2.bitwise_or(img_save, image_pad, dst=img_save)
        img_save = cv2.cvtColor(img_save, cv2.COLOR_BGR2RGB)
        return img_save

    def __getitem__(self, idx):
        dct = self.samples[idx]
        dct = CenterCrop((256, 256))(dct)
        dct = Normalize(normalize=True)(dct)
        img = dct['imgs']
        img = img.transpose(2, 0, 1)
        img = torch.from_numpy(img).float()

        dct["imgs"] = img
        return dct

    def __len__(self):
        return len(self.samples)


class WhirlPredictor(object):
    def __init__(self, device="cpu"):
        torch.backends.cudnn.deterministic = True
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        self.checkpoint_path = os.path.join(cur_dir, "checkpoints/iter_0006700.pth.tar")
        self.device = device
        self.batch_size = 16
        self.num_workers = 4

        self.net = MobileNetV3Small()
        state_dict = torch.load(self.checkpoint_path, map_location='cpu')
        sd = state_dict['state_dict']
        s = {}
        for key in sd:
            s[key.replace('module.', '')] = sd[key]
        self.net.load_state_dict(s, strict=True)
        if self.device == 'gpu':
            self.net = self.net.cuda()
        self.net.eval()

    def get_image(self, image_url):
        try:
            if image_url.startswith('http'):
                resp = requests.get(image_url)
                image = np.asarray(bytearray(resp.content))
                image = cv2.imdecode(image, cv2.IMREAD_COLOR)
            else:
                image = cv2.imread(image_url, cv2.IMREAD_COLOR)
        except:
            image = None

        return image

    def inference(self, sub_img, img):
        with torch.no_grad():
            dataset = CaptchaMergedDataset(sub_img, img)
            dataloader = DataLoader(dataset=dataset, batch_size=self.batch_size, num_workers=self.num_workers,
                                    pin_memory=True if self.device == "gpu" else False)
            max_score = -1
            max_angle = -1
            for dct in dataloader:
                img = dct["imgs"]
                angle = dct["angle"]

                if self.device == "gpu":
                    img = img.cuda(non_blocking=True)

                predict = self.net(img)
                act_score = torch.softmax(predict, dim=1)
                idx = torch.argmax(act_score[:, 1])
                if act_score[idx][1] > max_score:
                    max_score = act_score[idx][1].item()
                    max_angle = angle[idx].item()

            return max_angle

    def process(self, input_dict):
        sub_file_name = input_dict["img2"]  # 子图
        file_name = input_dict["img1"]  # 大图
        sub_img = self.get_image(sub_file_name)
        img = self.get_image(file_name)
        if sub_img is not None and img is not None:
            try:
                angle = self.inference(sub_img, img)
                res = {
                    "img1": input_dict["img1"],
                    "img2": input_dict["img2"],
                    "label_info": {
                        "angle": angle
                    }
                }
                ret_code = 200
                ret_msg = "OK"
            except Exception as e:
                print(e)
                ret_code = -1
                ret_msg = "Inner Error"
                res = None

            return ret_code, ret_msg, res

        else:
            ret_code = -1
            ret_msg = "Read Image Failed"
            res = None
            return ret_code, ret_msg, res


class Predictor3D(object):
    def __init__(self):
        torch.backends.cudnn.deterministic = True
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        self.checkpoint_path = os.path.join(cur_dir, "checkpoints/yolox_nano_416_3d_captcha_15k.pth")
        self.num_classes = 57
        self.conf_thre = 0.6
        self.test_size = (416, 416)
        self.device = "cpu"
        self.fp16 = False
        self.nms_thre = 0.65
        self.model = self.get_model()

    def get_model(self):
        def init_yolo(M):
            for m in M.modules():
                if isinstance(m, nn.BatchNorm2d):
                    m.eps = 1e-3
                    m.momentum = 0.03

        in_channels = [256, 512, 1024]
        backbone = YOLOPAFPN(0.33, 0.25, in_channels=in_channels, depthwise=True)
        head = YOLOXHead(self.num_classes, 0.25, in_channels=in_channels, depthwise=True)
        model = YOLOX(backbone, head)

        model.apply(init_yolo)
        model.head.initialize_biases(1e-2)
        ckpt = torch.load(self.checkpoint_path, map_location='cpu')
        model.load_state_dict(ckpt["model"])
        if self.device == 'gpu':
            model = model.cuda()
        model.eval()
        return model

    def val_transform(self, img, res, input_size):
        img, _ = self.preproc(img, input_size, swap=(2, 0, 1))

        return img, np.zeros((1, 5))

    def preproc(self, img, input_size, swap=(2, 0, 1)):
        if len(img.shape) == 3:
            padded_img = np.ones((input_size[0], input_size[1], 3), dtype=np.uint8) * 114
        else:
            padded_img = np.ones(input_size, dtype=np.uint8) * 114

        r = min(input_size[0] / img.shape[0], input_size[1] / img.shape[1])
        resized_img = cv2.resize(
            img,
            (int(img.shape[1] * r), int(img.shape[0] * r)),
            interpolation=cv2.INTER_LINEAR,
        ).astype(np.uint8)
        padded_img[: int(img.shape[0] * r), : int(img.shape[1] * r)] = resized_img

        padded_img = padded_img.transpose(swap)
        padded_img = np.ascontiguousarray(padded_img, dtype=np.float32)
        return padded_img, r

    def postprocess(self, prediction, num_classes, conf_thre=0.7, nms_thre=0.45, class_agnostic=False):
        box_corner = prediction.new(prediction.shape)
        box_corner[:, :, 0] = prediction[:, :, 0] - prediction[:, :, 2] / 2
        box_corner[:, :, 1] = prediction[:, :, 1] - prediction[:, :, 3] / 2
        box_corner[:, :, 2] = prediction[:, :, 0] + prediction[:, :, 2] / 2
        box_corner[:, :, 3] = prediction[:, :, 1] + prediction[:, :, 3] / 2
        prediction[:, :, :4] = box_corner[:, :, :4]

        output = [None for _ in range(len(prediction))]
        for i, image_pred in enumerate(prediction):
            if not image_pred.size(0):
                continue

            class_conf, class_pred = torch.max(image_pred[:, 5: 5 + num_classes], 1, keepdim=True)

            conf_mask = (image_pred[:, 4] * class_conf.squeeze() >= conf_thre).squeeze()

            detections = torch.cat((image_pred[:, :5], class_conf, class_pred.float()), 1)
            detections = detections[conf_mask]
            if not detections.size(0):
                continue

            if class_agnostic:
                nms_out_index = torchvision.ops.nms(
                    detections[:, :4],
                    detections[:, 4] * detections[:, 5],
                    nms_thre,
                )
            else:
                nms_out_index = torchvision.ops.batched_nms(
                    detections[:, :4],
                    detections[:, 4] * detections[:, 5],
                    detections[:, 6],
                    nms_thre,
                )

            detections = detections[nms_out_index]
            if output[i] is None:
                output[i] = detections
            else:
                output[i] = torch.cat((output[i], detections))

        return output

    def get_image(self, image_url):
        try:
            if image_url.startswith('http'):
                resp = requests.get(image_url)
                image = np.asarray(bytearray(resp.content))
                image = cv2.imdecode(image, cv2.IMREAD_COLOR)
            else:
                image = cv2.imread(image_url, cv2.IMREAD_COLOR)
        except:
            image = None

        return image

    def inference(self, img):
        img_info = {"id": 0}
        if isinstance(img, str):
            img_info["file_name"] = os.path.basename(img)
            img = cv2.imread(img)
        else:
            img_info["file_name"] = None

        height, width = img.shape[:2]

        img_info["height"] = height
        img_info["width"] = width
        img_info["raw_img"] = img

        ratio = min(self.test_size[0] / img.shape[0], self.test_size[1] / img.shape[1])
        img_info["ratio"] = ratio

        img, _ = self.val_transform(img, None, self.test_size)
        img = torch.from_numpy(img).unsqueeze(0)
        img = img.float()
        if self.device == "gpu":
            img = img.cuda()
            if self.fp16:
                img = img.half()  # to FP16

        with torch.no_grad():
            outputs = self.model(img)
            outputs = self.postprocess(
                outputs, self.num_classes, self.conf_thre,
                self.nms_thre
            )
        return outputs, img_info

    def visual(self, output, img_info):
        ratio = img_info["ratio"]
        output = output.cpu()

        bboxes = output[:, 0:4]

        bboxes /= ratio

        cls = output[:, 6]
        scores = output[:, 4] * output[:, 5]

        scores = scores.unsqueeze(-1)
        cls = cls.unsqueeze(-1)

        res = torch.cat((bboxes, scores, cls), dim=-1)

        return res

    def process(self, input_dict):
        file_name = input_dict["url1"]
        image = self.get_image(file_name)
        if image is not None:
            try:
                outputs, img_info = self.inference(image)
                if outputs is None or outputs[0] is None:
                    ret_code = -1
                    ret_msg = "Target Not Predicted"
                    res = None
                else:
                    outs = self.visual(outputs[0], img_info)
                    outs = outs.numpy().tolist()
                    # 归类
                    cls_bboxes = dict()
                    for out in outs:
                        cls = int(out[-1])
                        if cls not in cls_bboxes:
                            cls_bboxes[cls] = list()
                        bbox = [int(round(i)) for i in out[:4]]
                        bbox.append(out[4])
                        cls_bboxes[cls].append(bbox)

                    bboxes = None
                    # 根据数目排序
                    sorted_cls_bboxes = sorted(cls_bboxes.items(), key=lambda x: len(x[1]), reverse=True)
                    _, bboxes1 = sorted_cls_bboxes[0]
                    _, bboxes2 = sorted_cls_bboxes[1]

                    # 如果数目都等于2则返回置信度均值较高的
                    if len(bboxes1) == len(bboxes2) == 2:
                        sorted_cls_bboxes = sorted_cls_bboxes[:2]
                        sorted_cls_bboxes = sorted(sorted_cls_bboxes, key=lambda x: np.mean(np.asarray(x[1])[:, -1]),
                                                   reverse=True)
                        _, bboxes = sorted_cls_bboxes[0]
                        bboxes = [bbox[:4] for bbox in bboxes]

                    # 如果数目最大的大于了2， 则返回置信度较高的前两个框
                    elif len(bboxes1) > 2:
                        bboxes = sorted(bboxes1, key=lambda x: x[-1], reverse=True)
                        bboxes = [bbox[:4] for bbox in bboxes[:2]]

                    elif len(bboxes1) == 2:
                        bboxes = [bbox[:4] for bbox in bboxes1]

                    if bboxes is None:  # badcase，附一个默认值
                        bboxes = [
                            [112, 162, 196, 251],
                            [377, 113, 415, 160]
                        ]

                    res = {
                        "url1": input_dict["url1"],
                        "label_info": {
                            "bboxes": bboxes
                        }
                    }
                    ret_code = 200
                    ret_msg = "OK"
            except Exception as e:
                print(e)
                ret_code = -1
                ret_msg = "Inner Error"
                res = None

            return ret_code, ret_msg, res

        else:
            ret_code = -1
            ret_msg = "Read Image Failed"
            res = None
            return ret_code, ret_msg, res
