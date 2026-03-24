
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from src.ui import demo
    print("Launching Gradio UI...")
    demo.launch(server_name="0.0.0.0", server_port=7860, share=True)
