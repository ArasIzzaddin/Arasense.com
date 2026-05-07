import torch
import torch.nn.functional as F
from torch_geometric.nn import GCNConv

class ArasenseFloodGNN(torch.nn.Module):
    """
    Graph Neural Network for Flood Prediction.
    Uses GCN layers to propagate flood information along hydrological paths.
    """
    
    def __init__(self, num_node_features):
        super(ArasenseFloodGNN, self).__init__()
        
        # GCN Layers
        # Layer 1: Initial feature extraction
        self.conv1 = GCNConv(num_node_features, 16)
        
        # Layer 2: Propagate information to neighbors
        self.conv2 = GCNConv(16, 8)
        
        # Output Layer: Binary classification (Flood / No Flood)
        self.out = torch.nn.Linear(8, 1)

    def forward(self, data):
        x, edge_index = data.x, data.edge_index

        # Apply Graph Convolutions
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = F.dropout(x, p=0.2, training=self.training)
        
        x = self.conv2(x, edge_index)
        x = F.relu(x)
        
        # Final classification
        x = self.out(x)
        return torch.sigmoid(x)

if __name__ == "__main__":
    # Test with dummy data
    from torch_geometric.data import Data
    
    # Simulate a small graph (5 nodes, 4 features)
    x = torch.randn(5, 4)
    edge_index = torch.tensor([[0, 1, 1, 2], [1, 0, 2, 1]], dtype=torch.long)
    data = Data(x=x, edge_index=edge_index)
    
    model = ArasenseFloodGNN(num_node_features=4)
    output = model(data)
    
    print(f"Model output shape: {output.shape}")
    print(f"First 5 predictions:\n{output[:5]}")
    print("GNN model initialized and tested.")
