import pcbnew
import wx
from collections import defaultdict
import os
class AutoNetNamerPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Auto Net Namer"
        self.category = "Design Automation"
        self.description = "Automatically assign names to physically connected but unnamed nets"
        self.show_toolbar_button = True
        #self.icon_file_name = os.path.join(os.path.dirname(__file__), "auto_net_namer.png")
        try:
            self.icon_file_name = os.path.join(os.path.dirname(__file__), "auto_net_namer.png")
        except (FileNotFoundError, Exception):
            pass

    def Run(self):
        board = pcbnew.GetBoard()
        
        # Get all physically connected items without net names
        connected_items = self.find_connected_items(board)
        
        # Collect all already used net names
        used_net_names = {net.GetNetname() for net in board.GetNetInfo().NetsByNetcode().values() if net.GetNetname()}
        
        net_prefix = "AUTO_"
        counter = 1
        named_connections = 0
        
        # Create a new net for each connection group
        for connection_group in connected_items:
            if not connection_group:  # Skip empty groups
                continue
                
            # Check if this group already has a net name
            existing_net = self.get_existing_net(connection_group)
            if existing_net:
                continue  # Skip groups with existing nets
                
            group_has_conductors = any(isinstance(it, (pcbnew.PCB_TRACK, pcbnew.ZONE)) for it in connection_group)
            if not group_has_conductors:
                continue

            # Create a new net name
            while True:
                new_name = f"{net_prefix}{counter}"
                if new_name not in used_net_names:
                    break
                counter += 1
                
            # Create the net and assign it to all connected items
            new_net = board.FindNet(new_name)
            if not new_net:
                new_net = pcbnew.NETINFO_ITEM(board, new_name)
                board.Add(new_net)

            for item in connection_group:
                if isinstance(item, pcbnew.PAD):
                    # Only assign a net to pads when they’re actually connected to conductors
                    if item.GetNumber() in ["0", "MP"]:
                        gnd = board.FindNet("GND")
                        if not gnd:
                            gnd = pcbnew.NETINFO_ITEM(board, "GND")
                            board.Add(gnd)
                        item.SetNet(gnd)
                    else:
                        item.SetNet(new_net)
                else:
                    # Tracks/zones always get the new net
                    item.SetNet(new_net)
                
            used_net_names.add(new_name)
            counter += 1
            named_connections += 1
        
        # Refresh the PCB display
        pcbnew.Refresh()
        
        # Display results
        wx.MessageBox(
            f"Created {named_connections} new nets for previously unnamed connections.",
            "Auto Net Namer",
            wx.OK | wx.ICON_INFORMATION
        )

    def find_connected_items(self, board):
        """Find all physically connected but unnamed items"""
        # Get all items to check
        all_items = []
        
        # Collect all items with empty or default net names
        for track in board.GetTracks():
            net = track.GetNet()
            if not net or not net.GetNetname():  # Detect empty net name
                all_items.append(track)
        
        for zone in board.Zones():
            net = zone.GetNet()
            if not net or not net.GetNetname():  # Detect empty net name
                all_items.append(zone)
        
        for footprint in board.GetFootprints():
            for pad in footprint.Pads():
                net = pad.GetNet()
                if not net or not net.GetNetname():  # Detect empty net name
                    all_items.append(pad)
        
        # Use a set to track visited items
        visited = set()
        connected_groups = []
        
        for item in all_items:
            item_id = self.get_item_id(item)
            if item_id in visited:
                continue
                
            # Use BFS to find all connected items
            queue = [item]
            connected_group = []
            
            while queue:
                current = queue.pop(0)
                current_id = self.get_item_id(current)
                
                if current_id in visited:
                    continue
                    
                visited.add(current_id)
                connected_group.append(current)
                
                # Find physically connected items
                for other in all_items:
                    other_id = self.get_item_id(other)
                    if other_id in visited:
                        continue
                        
                    if self.are_physically_connected(board, current, other):
                        queue.append(other)
            
            if connected_group:
                connected_groups.append(connected_group)
                
        return connected_groups

    def get_item_id(self, item):
        """Generate a unique ID for each item"""
        return str(id(item))  # Use Python's object id to ensure uniqueness

    def are_physically_connected(self, board, item1, item2):
        """Improved physical connection detection"""
        # For pad-to-track or pad-to-zone connections
        if isinstance(item1, pcbnew.PAD) or isinstance(item2, pcbnew.PAD):
            pad = item1 if isinstance(item1, pcbnew.PAD) else item2
            other = item2 if isinstance(item1, pcbnew.PAD) else item1
            
            # Check if the pad is connected to a track
            if isinstance(other, pcbnew.PCB_TRACK):
                return pad.HitTest(other.GetStart()) or pad.HitTest(other.GetEnd())
            # Check if the pad is inside a copper zone
            elif isinstance(other, pcbnew.ZONE):
                return other.HitTest(pad.GetPosition())
        
        # For track-to-track connections
        elif isinstance(item1, pcbnew.PCB_TRACK) and isinstance(item2, pcbnew.PCB_TRACK):
            # Check for shared endpoints
            return (item1.GetStart() == item2.GetStart() or 
                    item1.GetStart() == item2.GetEnd() or
                    item1.GetEnd() == item2.GetStart() or
                    item1.GetEnd() == item2.GetEnd())
        
        # For zone-to-anything connections
        elif isinstance(item1, pcbnew.ZONE) or isinstance(item2, pcbnew.ZONE):
            zone = item1 if isinstance(item1, pcbnew.ZONE) else item2
            other = item2 if isinstance(item1, pcbnew.ZONE) else item1
            
            if isinstance(other, pcbnew.PCB_TRACK):
                return zone.HitTest(other.GetStart()) or zone.HitTest(other.GetEnd())
            elif isinstance(other, pcbnew.PAD):
                return zone.HitTest(other.GetPosition())
        
        return False

    def get_existing_net(self, items):
        """Check if the connection group already has a net assigned"""
        for item in items:
            net = item.GetNet()
            if net and net.GetNetname():  # Return the first existing net found
                return net
        return None

# Register the plugin
AutoNetNamerPlugin().register()
