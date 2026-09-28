import sys
import os

def read_lnk(filepath):
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(filepath)
        print("Shortcut File:", filepath)
        print("Target Path: ", shortcut.TargetPath)
        print("Arguments:   ", shortcut.Arguments)
        print("Working Dir: ", shortcut.WorkingDirectory)
        print("Icon Location:", shortcut.IconLocation)
    except Exception as e:
        print("Error reading lnk with win32com:", e)
        # Alternative using powershell command written to script
        import subprocess
        ps_script = f'''
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut("{filepath}")
        Write-Host "Target: $($shortcut.TargetPath)"
        Write-Host "Args: $($shortcut.Arguments)"
        Write-Host "Cwd: $($shortcut.WorkingDirectory)"
        '''
        ps_file = os.path.join(os.path.dirname(filepath), "temp_read_lnk.ps1")
        with open(ps_file, "w", encoding="utf-8") as f:
            f.write(ps_script)
        res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_file], capture_output=True, text=True)
        print(res.stdout)
        if os.path.exists(ps_file):
            os.remove(ps_file)

if __name__ == "__main__":
    read_lnk(r"C:\Users\Mauro\Desktop\Avatar AI.lnk")
