# Copyright (c) OpenMMLab. All rights reserved.
import argparse
import collections
import os.path as osp
import warnings
from collections import Iterable

import mmcv
from mmcv import DictAction
from sklearn.metrics import f1_score, precision_score, recall_score

from mmcls.datasets import build_dataset
from mmcls.models import build_classifier


def parse_args():
    parser = argparse.ArgumentParser(
        description='MMCls evaluate prediction success/fail')
    parser.add_argument('config', help='test config file path')
    parser.add_argument('result', help='test result json/pkl file')
    parser.add_argument('--out-dir', help='dir to store output files')
    parser.add_argument(
        '--topk',
        default=20,
        type=int,
        help='Number of images to select for success/fail')
    parser.add_argument(
        '--cfg-options',
        nargs='+',
        action=DictAction,
        help='override some settings in the used config, the key-value pair '
        'in xxx=yyy format will be merged into config file. If the value to '
        'be overwritten is a list, it should be like key="[a,b]" or key=a,b '
        'It also allows nested list/tuple values, e.g. key="[(a,b),(c,d)]" '
        'Note that the quotation marks are necessary and that no white space '
        'is allowed.')
    parser.add_argument(
        '--options',
        nargs='+',
        action=DictAction,
        help='override some settings in the used config, the key-value pair '
        'in xxx=yyy format will be merged into config file (deprecate), '
        'change to --cfg-options instead.')
    args = parser.parse_args()

    if args.options and args.cfg_options:
        raise ValueError(
            '--options and --cfg-options cannot be both '
            'specified, --options is deprecated in favor of --cfg-options')
    if args.options:
        warnings.warn('--options is deprecated in favor of --cfg-options')
        args.cfg_options = args.options

    return args


def save_imgs(result_dir, folder_name, results, model):
    full_dir = osp.join(result_dir, folder_name)
    mmcv.mkdir_or_exist(full_dir)
    mmcv.dump(results, osp.join(full_dir, folder_name + '.json'))

    # save imgs
    show_keys = ['pred_score', 'pred_class', 'gt_class']
    for result in results:
        result_show = dict((k, v) for k, v in result.items() if k in show_keys)
        outfile = osp.join(full_dir, osp.basename(result['filename']))
        model.show_result(result['filename'], result_show, out_file=outfile)


def main():
    args = parse_args()

    # load test results
    outputs = mmcv.load(args.result)
    assert ('pred_score' in outputs and 'pred_class' in outputs
            and 'pred_label' in outputs), \
        'No "pred_label", "pred_score" or "pred_class" in result file, ' \
        'please set "--out-items" in test.py'

    cfg = mmcv.Config.fromfile(args.config)
    if args.cfg_options is not None:
        cfg.merge_from_dict(args.cfg_options)

    model = build_classifier(cfg.model)

    # build the dataloader
    dataset = build_dataset(cfg.data.test)
    filenames = list()
    for info in dataset.data_infos:
        if info['img_prefix'] is not None:
            filename = osp.join(info['img_prefix'],
                                info['img_info']['filename'])
        else:
            filename = info['img_info']['filename']
        filenames.append(filename)
    gt_labels = list(dataset.get_gt_labels())
    gt_classes = [dataset.CLASSES[x] for x in gt_labels]

    outputs['filename'] = filenames
    outputs['gt_label'] = gt_labels
    outputs['gt_class'] = gt_classes

    outputs_list = list()
    for i in range(len(gt_labels)):
        output = dict()
        for k in outputs.keys():
            if not isinstance(outputs[k], Iterable):continue
            output[k] = outputs[k][i]
        outputs_list.append(output)

    # sort result
    outputs_list = sorted(outputs_list, key=lambda x: x['pred_score'])
    success = list()
    fail = list()
    pred_labels = []
    gt_labels = []
    for output in outputs_list:
        pred_label, gt_label = output['pred_label'], output['gt_label']
        pred_labels.append(pred_label)
        gt_labels.append(gt_label)
        if output['pred_label'] == output['gt_label']:
            success.append(output)
        else:
            fail.append(output)
    cell_f1_score = f1_score(gt_labels, pred_labels, average=None)
    cell_precision = precision_score(gt_labels, pred_labels, average=None)
    cell_recall = recall_score(gt_labels, pred_labels, average=None)
    print(cell_precision)
    print(cell_recall)
    print(cell_f1_score)
    success = success[:args.topk]
    fail = fail[:args.topk]
    #
    # save_imgs(args.out_dir, 'success', success, model)
    # save_imgs(args.out_dir, 'fail', fail, model)


if __name__ == '__main__':
    main()
