
import sys
import os
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.troubleshooting.indexer import TroubleshootingIndexer

def check_stats():
    indexer = TroubleshootingIndexer()
    stats = indexer.get_collection_stats()
    
    print("\n📊 Current Collection Statistics:")
    for coll_name, coll_info in stats.items():
        print(f"   {coll_name}: {coll_info.get('points_count', 'Error')}")

if __name__ == "__main__":
    check_stats()
