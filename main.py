from lupa import LuaRuntime
import sys
import re

def parse_lua(file_path):
    lua = LuaRuntime(unpack_returned_tuples=True)
    with open(file_path, 'r') as file:
        lua_content = file.read()
    return lua.eval(lua_content)

def format_authors(authors):
    return '; '.join(f"{name.split()[-1]}, {' '.join(name.split()[:-1])}" for name in authors.split(', '))

def generate_markdown(metadata):
    md = f"# {metadata['stats']['title']} - {format_authors(metadata['stats']['authors'])}\n\n"

    for bookmark in metadata['bookmarks'].values():
        if 'notes' not in bookmark:
            continue

        md += f"> {bookmark['notes']}\n\n"

        if 'text' in bookmark:
            md += f"Own thought:  \n{bookmark['text']}\n\n"

        md += "---\n\n"

    return md.strip()

def slugify(text):
    text = text.lower()
    return re.sub(r'[^\w\s-]', '', re.sub(r'[\s]+', '-', text)).strip('-')

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_lua_file>")
        sys.exit(1)

    lua_file = sys.argv[1]
    metadata = parse_lua(lua_file)
    markdown = generate_markdown(metadata)
    
    # Create a slugified filename based on the book title
    filename = slugify(metadata['stats']['title']) + '.md'
    
    # Save the markdown to the file
    with open(filename, 'w') as f:
        f.write(markdown)
    
    print(f"Markdown saved to {filename}")
