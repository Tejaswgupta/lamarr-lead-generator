import pyautogui
import time


def click_on_x_y(x, y, number_of_clicks, move=False):
    try:
        print(f"[INFO] Moving mouse to ({x}, {y}) and clicking with PyAutoGUI...")
        pyautogui.moveTo(x, y, duration=0.2)
        if move:
            pyautogui.mouseDown()
            time.sleep(0.1)
            pyautogui.mouseUp()
        for _ in range(number_of_clicks):
            pyautogui.click()
        print("[SUCCESS] Clicked  using PyAutoGUI")
        time.sleep(1)

        return True
    except Exception as e:
        print(f"[ERROR] PyAutoGUI click failed: {e}")
        return False
