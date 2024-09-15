import lua
import sys

def parse_lua(file_path):
    with open(file_path, 'r') as file:
        lua_content = file.read()
    return lua.decode(lua_content)

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

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_lua_file>")
        sys.exit(1)

    lua_file = sys.argv[1]
    metadata = parse_lua(lua_file)
    markdown = generate_markdown(metadata)
    print(markdown)
