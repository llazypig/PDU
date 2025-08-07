import cv2
import numpy as np

OBJ_THRESH, NMS_THRESH, IMG_SIZE = 0.20, 0.25, 640
CLASSES = ("other", "stand", "fall")


def filter_boxes(boxes, box_confidences, box_class_probs):
    """
    Filter boxes with object threshold.
    """
    box_confidences = box_confidences.reshape(-1)
    candidate, class_num = box_class_probs.shape

    class_max_score = np.max(box_class_probs, axis=-1)
    classes = np.argmax(box_class_probs, axis=-1)

    _class_pos = np.where(class_max_score* box_confidences >= OBJ_THRESH)
    scores = (class_max_score* box_confidences)[_class_pos]

    boxes = boxes[_class_pos]
    classes = classes[_class_pos]

    return boxes, classes, scores

def nms_boxes(boxes, scores):
    """Suppress non-maximal boxes.
    # Returns
        keep: ndarray, index of effective boxes.
    """
    x = boxes[:, 0]
    y = boxes[:, 1]
    w = boxes[:, 2] - boxes[:, 0]
    h = boxes[:, 3] - boxes[:, 1]

    areas = w * h
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)

        xx1 = np.maximum(x[i], x[order[1:]])
        yy1 = np.maximum(y[i], y[order[1:]])
        xx2 = np.minimum(x[i] + w[i], x[order[1:]] + w[order[1:]])
        yy2 = np.minimum(y[i] + h[i], y[order[1:]] + h[order[1:]])

        w1 = np.maximum(0.0, xx2 - xx1 + 0.00001)
        h1 = np.maximum(0.0, yy2 - yy1 + 0.00001)
        inter = w1 * h1

        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(ovr <= NMS_THRESH)[0]
        order = order[inds + 1]
    keep = np.array(keep)
    return keep

def dfl(position):
    # Distribution Focal Loss (DFL)
    # x = np.array(position)
    n,c,h,w = position.shape
    p_num = 4
    mc = c//p_num
    y = position.reshape(n,p_num,mc,h,w)
    
    # Vectorized softmax
    e_y = np.exp(y - np.max(y, axis=2, keepdims=True))  # subtract max for numerical stability
    y = e_y / np.sum(e_y, axis=2, keepdims=True)
    
    acc_metrix = np.arange(mc).reshape(1,1,mc,1,1)
    y = (y*acc_metrix).sum(2)
    return y
    

def box_process(position):
    grid_h, grid_w = position.shape[2:4]
    col, row = np.meshgrid(np.arange(0, grid_w), np.arange(0, grid_h))
    col = col.reshape(1, 1, grid_h, grid_w)
    row = row.reshape(1, 1, grid_h, grid_w)
    grid = np.concatenate((col, row), axis=1)
    stride = np.array([IMG_SIZE//grid_h, IMG_SIZE//grid_w]).reshape(1,2,1,1)

    position = dfl(position)
    box_xy  = grid +0.5 -position[:,0:2,:,:]
    box_xy2 = grid +0.5 +position[:,2:4,:,:]
    xyxy = np.concatenate((box_xy*stride, box_xy2*stride), axis=1)

    return xyxy

def yolov8_post_process(input_data):
    boxes, scores, classes_conf = [], [], []
    defualt_branch=3
    pair_per_branch = len(input_data)//defualt_branch
    # Python 忽略 score_sum 输出
    for i in range(defualt_branch):
        boxes.append(box_process(input_data[pair_per_branch*i]))
        classes_conf.append(input_data[pair_per_branch*i+1])
        scores.append(np.ones_like(input_data[pair_per_branch*i+1][:,:1,:,:], dtype=np.float32))

    def sp_flatten(_in):
        ch = _in.shape[1]
        _in = _in.transpose(0,2,3,1)
        return _in.reshape(-1, ch)

    boxes = [sp_flatten(_v) for _v in boxes]
    classes_conf = [sp_flatten(_v) for _v in classes_conf]
    scores = [sp_flatten(_v) for _v in scores]

    boxes = np.concatenate(boxes)
    classes_conf = np.concatenate(classes_conf)
    scores = np.concatenate(scores)

    # filter according to threshold
    boxes, classes, scores = filter_boxes(boxes, scores, classes_conf)

    # nms
    nboxes, nclasses, nscores = [], [], []
    for c in set(classes):
        inds = np.where(classes == c)
        b = boxes[inds]
        c = classes[inds]
        s = scores[inds]
        keep = nms_boxes(b, s)

        if len(keep) != 0:
            nboxes.append(b[keep])
            nclasses.append(c[keep])
            nscores.append(s[keep])

    if not nclasses and not nscores:
        return None, None, None

    boxes = np.concatenate(nboxes)
    classes = np.concatenate(nclasses)
    scores = np.concatenate(nscores)

    return boxes, classes, scores

def draw(image, boxes, scores, classes, ratio, padding):
    for box, score, cl in zip(boxes, scores, classes):
        top, left, right, bottom = box
        
        top = (top - padding[0])/ratio[0]
        left = (left - padding[1])/ratio[1]
        right = (right - padding[0])/ratio[0]
        bottom = (bottom - padding[1])/ratio[1]
        # print('class: {}, score: {}'.format(CLASSES[cl], score))
        # print('box coordinate left,top,right,down: [{}, {}, {}, {}]'.format(top, left, right, bottom))
        top = int(top)
        left = int(left)

        cv2.rectangle(image, (top, left), (int(right), int(bottom)), (255, 0, 0), 2)
        cv2.putText(image, '{0} {1:.2f}'.format(CLASSES[cl], score),
                    (top, left - 6),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 0, 255), 2)

def letterbox(im, new_shape=(640, 640), color=(0, 0, 0)):
    shape = im.shape[:2]  # current shape [height, width]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])

    ratio = r, r  # width, height ratios
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - \
        new_unpad[1]  # wh padding

    dw /= 2  # divide padding into 2 sides
    dh /= 2

    if shape[::-1] != new_unpad:  # resize
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right,
                            cv2.BORDER_CONSTANT, value=color)  # add border
    #return im
    return im, ratio, (left, top)

def myFunc(rknn_lite, IMG):
    # 读取ROI配置
    import json
    with open('/media/monster/PU/dynamic_detection-mj-dt1.8/rknn3588-yolov8/Demo/roi_config.json') as f:
        config = json.load(f)
    roi_points = np.array(config['config'][0]['roi'])
    
    # 读取所有no_roi区域
    no_roi_points = []
    for key in config['config'][0]:
        if key.startswith('no_roi_'):
            no_roi_points.append(np.array(config['config'][0][key]))
    
    original = IMG.copy()
    
    # 绘制ROI和no_roi边界线
    cv2.polylines(original, [roi_points], isClosed=True, color=(0, 255, 0), thickness=2)
    for points in no_roi_points:
        cv2.polylines(original, [points], isClosed=True, color=(0, 0, 255), thickness=2)
    
    # 创建ROI掩码并减去no_roi区域
    mask = np.zeros(IMG.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [roi_points], 255)
    for points in no_roi_points:
        cv2.fillPoly(mask, [points], 0)
    
    # 只处理ROI区域
    IMG = cv2.bitwise_and(IMG, IMG, mask=mask)
    
    try:
        # 调用 letterbox 函数
        # padded_img 是填充后的图像 (BGR)
        # ratio 是 (rw, rh) 缩放比例
        # pad 是 (pad_left, pad_top) 左侧和顶部的填充像素数
        padded_img, ratio, pad = letterbox(IMG, new_shape=(IMG_SIZE, IMG_SIZE), color=(0, 0, 0))
        
        # 将填充后的 BGR 图像转换为 RGB 格式以供模型输入
        padded_img_rgb = cv2.cvtColor(padded_img, cv2.COLOR_BGR2RGB)
        input_data = np.expand_dims(padded_img_rgb, 0)
    except Exception as e:
        print(f"Letterbox processing failed: {e}")
        return original, None, None, None
    
    outputs = rknn_lite.inference(inputs=[input_data], data_format=['nhwc'])

    boxes, classes, scores = yolov8_post_process(outputs)

    # 在绘制结果时检查是否在ROI内且不在no_roi内
    if boxes is not None:
        # ratio 是 (rw, rh)，pad 是 (pad_left, pad_top)
        rw, rh = ratio
        pad_left, pad_top = pad
        
        for box, score, cl in zip(boxes, scores, classes):
            # 将模型输出的坐标 (x1, y1, x2, y2) 从 640x640 尺寸映射回原始图像尺寸
            # 注意：模型输出的坐标是在 0-640 范围内 (即填充后图像的坐标)
            
            # 1. 首先，减去填充，得到在未填充图像中的坐标（相对于未填充图像的左上角）
            x1_unpadded = (box[0] - pad_left) / rw
            y1_unpadded = (box[1] - pad_top) / rh
            x2_unpadded = (box[2] - pad_left) / rw
            y2_unpadded = (box[3] - pad_top) / rh
            
            # 2. 转换为整数坐标 (这些坐标对应于 original 图像的尺寸)
            x1_original = int(x1_unpadded)
            y1_original = int(y1_unpadded)
            x2_original = int(x2_unpadded)
            y2_original = int(y2_unpadded)
            
            # 3. 计算中心点用于 ROI 检查 (使用映射回原始图像的坐标)
            box_center_original = ((x1_original + x2_original) // 2, (y1_original + y2_original) // 2)
            
            # 4. 检查中心点是否在 ROI 内且不在 no_roi 内
            in_roi = cv2.pointPolygonTest(roi_points, box_center_original, False) >= 0
            in_no_roi = any(cv2.pointPolygonTest(points, box_center_original, False) >= 0 for points in no_roi_points)
            
            # 5. 如果满足条件，则在 original 图像上绘制框和标签
            if in_roi and not in_no_roi:
                cv2.rectangle(original, (x1_original, y1_original), (x2_original, y2_original), (255, 0, 0), 2)
                cv2.putText(original, f"{CLASSES[cl]} {score:.2f}", (x1_original, y1_original - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    return original, boxes, classes, scores

    return original, None, None, None
