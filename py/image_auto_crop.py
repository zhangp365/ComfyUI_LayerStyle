from .imagefunc import *

NODE_NAME = 'ImageAutoCrop'

class ImageAutoCrop:

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(self):
        detect_mode = ['min_bounding_rect', 'max_inscribed_rect']
        ratio_list = ['1:1', '3:2', '4:3', '16:9', '2:3', '3:4', '9:16', 'custom']
        return {
            "required": {
                "image": ("IMAGE", ),  #
                "detect": (detect_mode,),
                "border_reserve": ("INT", {"default": 100, "min": -9999, "max": 9999, "step": 1}),
                "aspect_ratio": (ratio_list,),
                "proportional_width": ("INT", {"default": 2, "min": 1, "max": 999, "step": 1}),
                "proportional_height": ("INT", {"default": 1, "min": 1, "max": 999, "step": 1}),
                "background_color": ("STRING", {"default": "#FFFFFF"}),  # 背景颜色
                "edge_ultra_detail": ("BOOLEAN", {"default": False}),  # 是否修边缘
                "scale_to_longest_side": ("BOOLEAN", {"default": False}),  # 是否按长边缩放
                "longest_side": ("INT", {"default": 1024, "min": 4, "max": 999999, "step": 1}),
            },
            "optional": {
            }
        }

    RETURN_TYPES = ("IMAGE", "IMAGE",)
    RETURN_NAMES = ("cropped_image", "box_preview")
    FUNCTION = 'image_auto_crop'
    CATEGORY = '😺dzNodes/LayerUtility'
    OUTPUT_NODE = True

    def image_auto_crop(self, image, detect, border_reserve, aspect_ratio, proportional_width, proportional_height,
                     background_color, edge_ultra_detail, scale_to_longest_side, longest_side
                  ):

        ret_images = []
        ret_box_previews = []
        input_images = []
        input_masks = []
        crop_boxs = []

        for l in image:
            input_images.append(torch.unsqueeze(l, 0))
            m = tensor2pil(l)
            if m.mode == 'RGBA':
                input_masks.append(m.split()[-1])

        if len(input_masks) > 0 and len(input_masks) != len(input_images):
            input_masks = []
            log(f"Warning, {NODE_NAME} unable align alpha to image, drop it.", message_type='warning')

        if aspect_ratio == 'custom':
            ratio = proportional_width / proportional_height
        else:
            s = aspect_ratio.split(":")
            ratio = int(s[0]) / int(s[1])
        side_limit = longest_side if scale_to_longest_side else 0

        for i in range(len(input_images)):
            _image = tensor2pil(input_images[i]).convert('RGB')
            if len(input_masks) > 0:
                _mask = input_masks[i]
            else:
                _mask = RMBG(_image)
                if edge_ultra_detail:
                    _mask = tensor2pil(mask_edge_detail(input_images[i], pil2tensor(_mask), 8, 0.01, 0.99))
            bluredmask = gaussian_blur(_mask, 20).convert('L')
            x = 0
            y = 0
            width = 0
            height = 0
            x_offset = 0
            y_offset = 0
            if detect == "min_bounding_rect":
                (x, y, width, height) = min_bounding_rect(bluredmask)
            if detect == "max_inscribed_rect":
                (x, y, width, height) = max_inscribed_rect(bluredmask)
            canvas_width, canvas_height = _image.size
            x1 = x - border_reserve
            y1 = y - border_reserve
            x2 = x + width + border_reserve
            y2 = y + height + border_reserve
            if x1 < 0:
                canvas_width -= x1
                x_offset = -x1
            if y1 < 0:
                canvas_height -= y1
                y_offset = -y1
            if x2 > _image.width:
                canvas_width += x2 - _image.width
            if y2 > _image.height:
                canvas_height += y2 - _image.height
            crop_box = (x1 + x_offset, y1 + y_offset, width + border_reserve*2, height + border_reserve*2)
            crop_boxs.append(crop_box)
            if len(crop_boxs) > 0:    # 批量图强制使用同一尺寸
                crop_box = crop_boxs[0]
            target_width, target_height = calculate_side_by_ratio(crop_box[2], crop_box[3], ratio,
                                                                  longest_side=side_limit)
            _canvas = Image.new('RGB', size=(canvas_width, canvas_height), color=background_color)
            if edge_ultra_detail:
                _image = pixel_spread(_image, _mask)
            _canvas.paste(_image, box=(x_offset, y_offset), mask=_mask.convert('L'))
            preview_image = Image.new('RGB', size=(canvas_width, canvas_height), color='gray')
            preview_image.paste(_mask, box=(x_offset, y_offset))
            preview_image = draw_rect(preview_image,
                                      crop_box[0], crop_box[1], crop_box[2], crop_box[3],
                                      line_color="#F00000", line_width=(canvas_width + canvas_height)//200)

            ret_image = _canvas.crop((crop_box[0], crop_box[1], crop_box[0]+crop_box[2], crop_box[1]+crop_box[3]))
            ret_image = fit_resize_image(ret_image, target_width, target_height,
                                         fit='letterbox', resize_sampler=Image.LANCZOS,
                                         background_color=background_color)
            ret_images.append(pil2tensor(ret_image))
            ret_box_previews.append(pil2tensor(preview_image))

        log(f"{NODE_NAME} Processed {len(ret_images)} image(s).", message_type='finish')
        return (torch.cat(ret_images, dim=0), torch.cat(ret_box_previews, dim=0),)


NODE_CLASS_MAPPINGS = {
    "LayerUtility: ImageAutoCrop": ImageAutoCrop
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LayerUtility: ImageAutoCrop": "LayerUtility: ImageAutoCrop"
}