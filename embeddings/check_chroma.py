import chromadb
client = chromadb.PersistentClient(path='/mnt/c/Users/user/projects/meep-kb/db/chroma')
cols = client.list_collections()
print("Collections:")
for c in cols:
    print(f"  {c.name}: {c.count()}건, metadata={c.metadata}")
