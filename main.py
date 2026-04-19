from src.parser.parser import MapParser

parser = MapParser("maps/easy/01_linear_path.txt")
graph = parser.parse()

print(graph.zones)
