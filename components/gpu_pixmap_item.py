from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QMatrix4x4, QPixmap
from PyQt6.QtWidgets import QGraphicsPixmapItem
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtOpenGL import QOpenGLShaderProgram, QOpenGLShader, QOpenGLTexture

class GPUPixmapItem(QGraphicsPixmapItem):
    """
    A GraphicsItem that draws a pixmap using an OpenGL shader for 
    real-time image adjustments (Brightness, Contrast, Gamma, Saturation).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.shader = None
        self.gpu_enabled = False
        self.current_image = QImage()
        
        # Image adjustment parameters
        self.brightness = 0.0    # -1.0 to 1.0
        self.contrast = 1.0      # 0.0 to 2.0
        self.gamma = 1.0         # 0.1 to 3.0
        self.saturation = 1.0    # 0.0 to 2.0
        
        self.texture = None
        self._last_pixmap_id = None
        self._new_image_loaded = False

    def __del__(self):
        if self.texture:
            self.texture.destroy()

    def boundingRect(self):
        if not self.current_image.isNull():
            from PyQt6.QtCore import QRectF
            return QRectF(0.0, 0.0, float(self.current_image.width()), float(self.current_image.height()))
        return super().boundingRect()

    def setImage(self, image):
        if not image.isNull():
            self.current_image = image.convertToFormat(QImage.Format.Format_RGBA8888)
            pix = self.pixmap()
            if pix.isNull() or pix.width() != image.width() or pix.height() != image.height():
                super().setPixmap(QPixmap.fromImage(self.current_image))
            self._new_image_loaded = True
            self.update()
        else:
            self.current_image = QImage()
            super().setPixmap(QPixmap())
            self._new_image_loaded = False
            self.update()

    def setPixmap(self, pixmap):
        super().setPixmap(pixmap)
        if not pixmap.isNull():
            self.current_image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            self._new_image_loaded = True
        else:
            self.current_image = QImage()
            self._new_image_loaded = False
        self.update()

    def update_params(self, b, c, g, s):
        self.brightness = b / 100.0
        self.contrast = c
        self.gamma = g
        self.saturation = s
        self.update()

    def _init_shader(self):
        if self.shader is not None:
            return
            
        self.shader = QOpenGLShaderProgram()
        
        v_shader = """#version 120
        attribute vec4 vertex;
        attribute vec2 texCoord;
        uniform mat4 matrix;
        varying vec2 v_texCoord;
        void main(void) {
            gl_Position = matrix * vertex;
            v_texCoord = texCoord;
        }
        """
        
        f_shader = """#version 120
        varying vec2 v_texCoord;
        uniform sampler2D u_texture;
        uniform float u_opacity;
        
        uniform float u_brightness;
        uniform float u_contrast;
        uniform float u_gamma;
        uniform float u_saturation;
        
        void main(void) {
            vec4 color = texture2D(u_texture, v_texCoord);
            
            // 1. Brightness & Contrast
            // Apply (x - 0.5) * contrast + 0.5 + brightness
            vec3 rgb = color.rgb;
            rgb = (rgb - 0.5) * u_contrast + 0.5 + u_brightness;
            
            // 2. Gamma
            if (u_gamma != 1.0 && u_gamma > 0.0) {
                rgb = pow(max(rgb, vec3(0.0)), vec3(1.0 / u_gamma));
            }
            
            // 3. Saturation
            if (u_saturation != 1.0) {
                float gray = dot(rgb, vec3(0.299, 0.587, 0.114));
                rgb = mix(vec3(gray), rgb, u_saturation);
            }
            
            gl_FragColor = vec4(rgb, color.a * u_opacity);
        }
        """
        
        if not self.shader.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, v_shader):
            print("Vertex shader error:", self.shader.log())
        if not self.shader.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, f_shader):
            print("Fragment shader error:", self.shader.log())
            
        if not self.shader.link():
            print("Shader link error:", self.shader.log())
 
    def paint(self, painter, option, widget):
        try:
            if not self.gpu_enabled or self.pixmap().isNull() or self.current_image.isNull():
                super().paint(painter, option, widget)
                return
 
            # Ensure we are rendering in an OpenGL context
            if not isinstance(widget, QOpenGLWidget):
                super().paint(painter, option, widget)
                return
 
            self._init_shader()
            
            if not self.shader or not self.shader.isLinked():
                super().paint(painter, option, widget)
                return
 
            pix = self.pixmap()
            img = self.current_image
            
            # Update texture if image dimensions changed
            texture_recreated = False
            if self.texture is None or self.texture.width() != img.width() or self.texture.height() != img.height():
                if self.texture:
                    self.texture.destroy()
                self.texture = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
                self.texture.setSize(img.width(), img.height())
                self.texture.setFormat(QOpenGLTexture.TextureFormat.RGBA8_UNorm)
                self.texture.allocateStorage()
                self.texture.setMinificationFilter(QOpenGLTexture.Filter.Linear)
                self.texture.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
                self.texture.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
                texture_recreated = True
            
            if self._new_image_loaded or texture_recreated:
                # Optimized update: upload CPU image memory directly to GPU texture (no readback!)
                self.texture.setData(QOpenGLTexture.PixelFormat.RGBA, QOpenGLTexture.PixelType.UInt8, img.constBits())
                self._new_image_loaded = False

            painter.beginNativePainting()
            
            self.shader.bind()
            
            # Get attribute locations
            v_loc = self.shader.attributeLocation("vertex")
            t_loc = self.shader.attributeLocation("texCoord")
            
            # Setup Projection Matrix
            matrix = QMatrix4x4(painter.combinedTransform())
            
            proj = QMatrix4x4()
            proj.ortho(0, widget.width(), widget.height(), 0, -1, 1)
            
            self.shader.setUniformValue("matrix", proj * matrix)
            self.shader.setUniformValue("u_brightness", self.brightness)
            self.shader.setUniformValue("u_contrast", self.contrast)
            self.shader.setUniformValue("u_gamma", self.gamma)
            self.shader.setUniformValue("u_saturation", self.saturation)
            self.shader.setUniformValue("u_opacity", painter.opacity())
            self.shader.setUniformValue("u_texture", 0)

            self.texture.bind(0)
            
            # Draw Quad
            w = float(pix.width())
            h = float(pix.height())
            
            import numpy as np
            vertices = np.array([0.0, 0.0, w, 0.0, w, h, 0.0, h], dtype=np.float32).reshape(-1, 2)
            texCoords = np.array([0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0], dtype=np.float32).reshape(-1, 2)
            
            from PyQt6.QtOpenGL import QOpenGLFunctions_2_1
            gl = QOpenGLFunctions_2_1()
            gl.initializeOpenGLFunctions()
            
            # Ensure viewport is correct
            gl.glViewport(0, 0, widget.width(), widget.height())
            
            self.shader.enableAttributeArray(v_loc)
            self.shader.enableAttributeArray(t_loc)
            
            # Use 2-argument call, shape will define the tuple size
            self.shader.setAttributeArray(v_loc, vertices)
            self.shader.setAttributeArray(t_loc, texCoords)
            
            gl.glDrawArrays(0x0006, 0, 4) # GL_TRIANGLE_FAN is 0x0006
            
            self.shader.disableAttributeArray(v_loc)
            self.shader.disableAttributeArray(t_loc)
            
            self.shader.release()
            self.texture.release()
            
            painter.endNativePainting()
            
        except Exception as e:
            # Fallback to standard painting on error
            print(f"Shader paint error: {e}")
            super().paint(painter, option, widget)
