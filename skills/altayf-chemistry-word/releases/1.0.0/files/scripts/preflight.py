"""Report local capabilities. No installs, downloads, external requests or Word mutations."""
import importlib.util,platform,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    print(json.dumps({'python':platform.python_version(),'platform':platform.system(),
      'modules':{m:bool(importlib.util.find_spec(m)) for m in ['docx','lxml','PIL','pymupdf']},
      'template':(ROOT/'assets/templates/lesson-frame.docx').exists(),
      'native_word_probe':'On Windows use [Type]::GetTypeFromProgID("Word.Application") read-only; COM registration is not proof export will work.',
      'font_probe':'Verify Dubai is available to the actual renderer (system/user/Office fonts). Do not silently substitute it; inspect the rendered result.',
      'image_generation':'Use the available built-in image generation tool; availability must be discovered by the agent.'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
