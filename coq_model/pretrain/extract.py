import re, json
from tqdm import tqdm
from ..java2impp import javalang, visit

def extract_java_code_from_dicts(dict_list):
    # Define a placeholder for java code
    placeholder = "<JAVA_CODE>"

    # Regular expression to match java code blocks
    java_code_pattern = re.compile(r"```java\n.*?```", re.DOTALL)

    for item in tqdm(dict_list):
        if 'output' in item:
            # Extract java code from the output field
            java_code_matches = java_code_pattern.findall(item['output'])
            
            # Remove the enclosing ```java and ``` from the matches
            java_code_matches = [code[8:-3].strip() for code in java_code_matches]

            # Save the extracted java code to the new field
            item['java_list'] = java_code_matches

            # Replace the java code in the output field with the placeholder
            item['output'] = java_code_pattern.sub(placeholder, item['output'])
            item['text'] = item['instruction'] + '\n\n' + item['output']

    return dict_list

newdatas = []
placeholder = "<JAVA_CODE>"
with open("opencoder-sft-java.json", 'r') as f:
    data = json.load(f)
    data = extract_java_code_from_dicts(data)
for i in tqdm(range(len(data))):
    try:
        newdata = {}
        newdata['text'] = data[i]['text']
        assert len(data[i]['java_list']) == 1
        javacode = data[i]['java_list'][0]
        tree = javalang.parse.parse(javacode)
        program = visit(tree)
        javacode = program.to_java()
        newdata['javacode']=javacode
        newdatas.append(newdata)
    except Exception as e:
        continue

print(f"{len(newdatas)} samples are generated")
print(f"Example: {json.dumps(newdatas[0], indent=4, ensure_ascii=False)}")