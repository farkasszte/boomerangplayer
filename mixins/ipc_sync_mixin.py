"""
IPCSyncMixin — Multi-Instance Peer-to-Peer Playback Synchronization using UDP local sockets.
"""

import uuid
import json
from PyQt6.QtCore import Qt
from PyQt6.QtNetwork import QUdpSocket, QHostAddress


class IPCSyncMixin:
    def init_ipc_sync(self):
        self.sync_instance_id = uuid.uuid4().hex
        self.sync_offset = None
        self._block_broadcast = False
        
        # Create UDP socket
        self.udp_socket = QUdpSocket(self)
        
        # Bind to port 28357 with share and reuse flags on AnyIPv4 to receive multicast
        self.udp_socket.bind(
            QHostAddress(QHostAddress.SpecialAddress.AnyIPv4), 
            28357, 
            QUdpSocket.BindFlag.ShareAddress | QUdpSocket.BindFlag.ReuseAddressHint
        )
        
        # Join local-scoped multicast group
        self.multicast_group = QHostAddress("239.255.43.21")
        self.udp_socket.joinMulticastGroup(self.multicast_group)
        
        self.udp_socket.readyRead.connect(self.handle_incoming_sync)
        print(f"[IPCSync] Bound UDP socket and joined multicast 239.255.43.21 on port 28357. Instance ID: {self.sync_instance_id}")
        if hasattr(self, 'update_sync_lock_button_style'):
            self.update_sync_lock_button_style()

    def broadcast_sync_event(self, action, value=None):
        if not getattr(self, 'isSyncLocked', True) or getattr(self, '_block_broadcast', False):
            return
            
        payload = {
            "sender_id": self.sync_instance_id,
            "action": action,
            "value": value,
            "frame": getattr(self, 'current_cache_index', 0)
        }
        
        data = json.dumps(payload).encode('utf-8')
        
        # Send multicast datagram to all local instances on port 28357
        self.udp_socket.writeDatagram(
            data, 
            self.multicast_group, 
            28357
        )

    def force_frame_sync_broadcast(self):
        # Reset local offset to 0 as we are aligning everything to our current frame
        self.sync_offset = 0
        
        payload = {
            "sender_id": self.sync_instance_id,
            "action": "force_frame_sync",
            "value": None,
            "frame": getattr(self, 'current_cache_index', 0)
        }
        
        data = json.dumps(payload).encode('utf-8')
        
        # Broadcast via multicast
        if hasattr(self, 'multicast_group') and hasattr(self, 'udp_socket'):
            self.udp_socket.writeDatagram(
                data, 
                self.multicast_group, 
                28357
            )
            print(f"[IPCSync] Broadcasted force_frame_sync at frame: {payload['frame']}")

    def handle_incoming_sync(self):
        while self.udp_socket.hasPendingDatagrams():
            datagram, host, port = self.udp_socket.readDatagram(
                self.udp_socket.pendingDatagramSize()
            )
            
            try:
                # datagram is a bytes object in PyQt6
                payload = json.loads(datagram.decode('utf-8'))
            except Exception as e:
                print(f"[IPCSync] Error decoding UDP datagram: {e}")
                continue
                
            sender_id = payload.get("sender_id")
            action = payload.get("action")
            value = payload.get("value")
            remote_frame = payload.get("frame", 0)
            
            # 1. Ignore own echoed packets
            if sender_id == self.sync_instance_id:
                continue
                
            # 2. Ignore if sync lock is disabled locally
            if not getattr(self, 'isSyncLocked', True):
                continue
                
            # Block broadcast loop recursion
            self._block_broadcast = True
            
            try:
                # 3. Synchronize Offset on seek/play/sync_state/sync_reply
                if action in ["sync_state", "sync_reply"]:
                    self.sync_offset = getattr(self, 'current_cache_index', 0) - remote_frame
                    print(f"[IPCSync] Offset synchronized via {action} to: {self.sync_offset} frames relative to remote")
                elif action in ["seek", "play"] and self.sync_offset is None:
                    self.sync_offset = getattr(self, 'current_cache_index', 0) - remote_frame
                    print(f"[IPCSync] Offset synchronized via {action} to: {self.sync_offset} frames relative to remote")

                if action == "sync_state":
                    # Send our state back so the sender can establish theirs
                    self._block_broadcast = False
                    try:
                        self.broadcast_sync_event("sync_reply", None)
                    finally:
                        self._block_broadcast = True

                elif action == "sync_reply":
                    # Already synchronized offset above
                    pass

                elif action == "play":
                    if value:
                        speed = value.get("speed", 100)
                        if hasattr(self, 'speedSlider'):
                            self.speedSlider.setValue(speed)
                        
                        is_forward = value.get("isForward", True)
                        self.isForward = is_forward

                    # Align seek position before playing
                    if self.sync_offset is not None and hasattr(self, 'total_frames') and self.total_frames > 0:
                        target_frame = remote_frame + self.sync_offset
                        target_frame = max(0, min(self.total_frames - 1, target_frame))
                        
                        if target_frame != self.current_cache_index:
                            
                            self.set_position(target_frame)

                    
                    self._start_playback()

                elif action == "pause":
                    
                    self.stop_playback()

                elif action == "step":
                    if value is not None:
                        
                        self.step_frame(int(value))

                elif action == "seek":
                    if self.sync_offset is not None and hasattr(self, 'total_frames') and self.total_frames > 0:
                        target_frame = remote_frame + self.sync_offset
                        target_frame = max(0, min(self.total_frames - 1, target_frame))
                        
                        if target_frame != self.current_cache_index:
                            
                            self.set_position(target_frame)

                elif action == "speed":
                    if value is not None and hasattr(self, 'speedSlider'):
                        self.speedSlider.setValue(int(value))

                elif action == "force_frame_sync":
                    self.sync_offset = 0
                    if hasattr(self, 'total_frames') and self.total_frames > 0:
                        target_frame = max(0, min(self.total_frames - 1, remote_frame))
                        
                        if target_frame != self.current_cache_index:
                            
                            self.set_position(target_frame)

            except Exception as e:
                print(f"[IPCSync] Error processing action {action}: {e}")
            finally:
                self._block_broadcast = False
