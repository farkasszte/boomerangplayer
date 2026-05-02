import qfluentwidgets
print(f"setThemeColor in qfluentwidgets: {'setThemeColor' in dir(qfluentwidgets)}")
if 'setThemeColor' in dir(qfluentwidgets):
    print("setThemeColor found!")
else:
    # check in theme
    from qfluentwidgets import ThemeColor
    print(f"ThemeColor in qfluentwidgets: {ThemeColor}")
