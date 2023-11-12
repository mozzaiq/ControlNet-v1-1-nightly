from celery import Celery
from celery.signals import worker_process_init
import cv2

celery_app = Celery(
    "worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

backend = None

@worker_process_init.connect
def load_model_at_worker_init(*args, **kwargs):
    import os
    print("Current working directory:", os.getcwd())
    import sys
    sys.path.append(".")
    global backend
    import backend
    print('Loading model...')
    backend.init_model()
    print('Model loaded.')
    
@celery_app.task(bind=True)
def handle_image_processing(self, image_filename, mask_filename, prompt, seed, num_images, resolution, num_steps):
    image = cv2.imread(image_filename)[:,:,[2,1,0]]
    mask = cv2.imread(mask_filename)
    if mask.shape[0] != image.shape[0] or mask.shape[1] != image.shape[1]:
        raise Exception(f"Expected image and mask to be of the same size, but got HxWxC {image.shape} vs. {mask.shape}")
    print("#### TASK #####")
    try:
        def update_state(state_dict):
             self.update_state(state='PROGRESS', meta=state_dict)

        results: List[np.ndarray] = backend.process(
            input_image_and_mask={
                "image": image,
                "mask": mask
            }, 
            prompt=prompt,
            a_prompt="best quality",
            n_prompt="lowres, bad anatomy, bad hands, cropped, worst quality",
            num_samples=num_images,
            image_resolution=resolution,
            ddim_steps=num_steps,
            guess_mode=False,
            strength=1,
            scale=9,
            seed=seed,
            eta=1,
            mask_blur=5,
            update_state_fn=update_state,
        )
        images = []
        for i in range(len(results)):
            res_name = f"/tmp/tmp_{self.request.id}_result_{i}.png"
            cv2.imwrite(res_name, results[i][:,:,[2,1,0]])
            images.append(res_name)
        return {"image_filenames": images, "num_images": len(results)}
    except Exception as e:
        print(f"*** Exception in job {self.request.id}")
        raise
        # print(e)
    finally:
        # TODO clean-up
        pass
