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
        self.icon_file_name = os.path.join(os.path.dirname(__file__), "auto_net_namer.png")

    def Run(self):
        board = pcbnew.GetBoard()
        
        # 获取所有未命名的物理连接
        connected_items = self.find_connected_items(board)
        
        # 收集已使用的网络名称
        used_net_names = {net.GetNetname() for net in board.GetNetInfo().NetsByNetcode().values() if net.GetNetname()}
        
        net_prefix = "AUTO_"
        counter = 1
        named_connections = 0
        
        # 为每个连接组创建网络
        for connection_group in connected_items:
            if not connection_group:  # 跳过空组
                continue
                
            # 检查是否已经有网络名称
            existing_net = self.get_existing_net(connection_group)
            if existing_net:
                continue  # 跳过已有网络的连接
                
            # 创建新网络
            while True:
                new_name = f"{net_prefix}{counter}"
                if new_name not in used_net_names:
                    break
                counter += 1
                
            # 创建网络并分配给所有连接项
            new_net = board.FindNet(new_name)
            if not new_net:
                new_net = pcbnew.NETINFO_ITEM(board, new_name)
                board.Add(new_net)
                
            for item in connection_group:
                item.SetNet(new_net)
                
            used_net_names.add(new_name)
            counter += 1
            named_connections += 1
        
        # 更新PCB
        pcbnew.Refresh()
        
        # 显示结果
        wx.MessageBox(
            f"Created {named_connections} new nets for previously unnamed connections.",
            "Auto Net Namer",
            wx.OK | wx.ICON_INFORMATION
        )

    def find_connected_items(self, board):
        """查找所有物理连接但未命网络的项"""
        # 获取所有需要检查的项
        all_items = []
        
        # 收集所有未命名或默认命名的项
        for track in board.GetTracks():
            net = track.GetNet()
            if not net or not net.GetNetname():  # 检测空网络名
                all_items.append(track)
        
        for zone in board.Zones():
            net = zone.GetNet()
            if not net or not net.GetNetname():  # 检测空网络名
                all_items.append(zone)
        
        for footprint in board.GetFootprints():
            for pad in footprint.Pads():
                net = pad.GetNet()
                if not net or not net.GetNetname():  # 检测空网络名
                    all_items.append(pad)
        
        # 使用字典来跟踪访问状态
        visited = set()
        connected_groups = []
        
        for item in all_items:
            item_id = self.get_item_id(item)
            if item_id in visited:
                continue
                
            # 使用BFS查找所有连接的项
            queue = [item]
            connected_group = []
            
            while queue:
                current = queue.pop(0)
                current_id = self.get_item_id(current)
                
                if current_id in visited:
                    continue
                    
                visited.add(current_id)
                connected_group.append(current)
                
                # 查找物理连接的项
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
        """为每个项生成唯一标识符"""
        return str(id(item))  # 直接使用对象id确保唯一性

    def are_physically_connected(self, board, item1, item2):
        """改进的物理连接检测"""
        # 对于焊盘和导线/焊盘的连接
        if isinstance(item1, pcbnew.PAD) or isinstance(item2, pcbnew.PAD):
            pad = item1 if isinstance(item1, pcbnew.PAD) else item2
            other = item2 if isinstance(item1, pcbnew.PAD) else item1
            
            # 检查焊盘是否与导线连接
            if isinstance(other, pcbnew.PCB_TRACK):
                return pad.HitTest(other.GetStart()) or pad.HitTest(other.GetEnd())
            # 检查焊盘是否在铺铜区域内
            elif isinstance(other, pcbnew.ZONE):
                return other.HitTest(pad.GetPosition())
        
        # 对于导线和导线的连接
        elif isinstance(item1, pcbnew.PCB_TRACK) and isinstance(item2, pcbnew.PCB_TRACK):
            # 检查是否有共享端点
            return (item1.GetStart() == item2.GetStart() or 
                    item1.GetStart() == item2.GetEnd() or
                    item1.GetEnd() == item2.GetStart() or
                    item1.GetEnd() == item2.GetEnd())
        
        # 对于铺铜和其他项
        elif isinstance(item1, pcbnew.ZONE) or isinstance(item2, pcbnew.ZONE):
            zone = item1 if isinstance(item1, pcbnew.ZONE) else item2
            other = item2 if isinstance(item1, pcbnew.ZONE) else item1
            
            if isinstance(other, pcbnew.PCB_TRACK):
                return zone.HitTest(other.GetStart()) or zone.HitTest(other.GetEnd())
            elif isinstance(other, pcbnew.PAD):
                return zone.HitTest(other.GetPosition())
        
        return False

    def get_existing_net(self, items):
        """检查连接组中是否已有网络"""
        for item in items:
            net = item.GetNet()
            if net and net.GetNetname():  # 只返回有名称的网络
                return net
        return None

# 注册插件
AutoNetNamerPlugin().register()