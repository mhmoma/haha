import requests
import json

def get_ksampler_options():
    """获取 ComfyUI KSampler 节点的可用采样器和调度器选项"""
    try:
        response = requests.get("http://127.0.0.1:8188/object_info/KSampler")
        response.raise_for_status()
        data = response.json()
        
        ksampler_info = data.get("KSampler", {})
        required_inputs = ksampler_info.get("input", {}).get("required", {})
        
        samplers = required_inputs.get("sampler_name", [[]])[0]
        schedulers = required_inputs.get("scheduler", [[]])[0]
        
        print("--- Available Samplers ---")
        print(json.dumps(samplers, indent=2))
        
        print("\n--- Available Schedulers ---")
        print(json.dumps(schedulers, indent=2))
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from ComfyUI: {e}")
    except (KeyError, IndexError) as e:
        print(f"Error parsing the API response: {e}")

if __name__ == "__main__":
    get_ksampler_options()
