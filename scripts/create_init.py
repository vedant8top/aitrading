import os
os.makedirs('src/regime_detection', exist_ok=True)
with open('src/regime_detection/__init__.py', 'w') as f:
    f.write('"""Market Regime Detection Framework v1."""\n\n__version__ = "1.0.0"\n')
print('File created')