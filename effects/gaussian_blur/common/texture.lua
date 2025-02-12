local TAG = "TextureRender"

local DEF_RenderType_Image = 0
local DEF_RenderType_Color = 1

local TextureRender = {
    vs = [[
        precision highp float;
        uniform mat4 uMVP;
        attribute vec4 aPosition;
        attribute vec4 aTextureCoord;
        attribute vec4 aColor;
        varying vec2 vTexCoord;
        void main()
        {
            gl_Position = uMVP * aPosition;
            vTexCoord = aTextureCoord.xy;
        }
        ]],
    vs_antialias = [[
        precision highp float;
        uniform mat4 uMVP;
        attribute vec4 aPosition;
        attribute vec4 aTextureCoord;
        varying vec2 vTexCoord;
        void main()
        {
            gl_Position = uMVP * vec4(aPosition.xyz, 1.0);
            vTexCoord = aTextureCoord.xy;
        }
        ]],
    fs_animate = [[
        precision highp float;
        varying vec2 vTexCoord;

        uniform float uTileX;
        uniform float uTileY;
        uniform float uAnimFPS;
        uniform float uTimestamp;
        uniform sampler2D uTexture0;
        uniform vec4 uColor;
        
        void main()
        {
            vec2 uv = vTexCoord;
            int idx = int(mod(uTimestamp * uAnimFPS / 1000.0, uTileX * uTileY));
            int rowIdx = int(mod(float(idx) / uTileX, uTileY));
            int colIdx = int(mod(float(idx), uTileX));

            uv.x = uv.x / uTileX + float(colIdx) / uTileX;
            uv.y = uv.y / uTileY + float(rowIdx) / uTileY;

            vec4 color = texture2D(uTexture0, uv);
            gl_FragColor = color * uColor;
        }
        ]],
        
   fs_simple = [[
        precision highp float;
        varying vec2 vTexCoord;

        uniform sampler2D uTexture0;
        uniform vec4 uColor;
        uniform float uType;

        vec2 mirrorRepeatUV(vec2 uv)
        {
            vec2 mUV = mod(abs(floor(uv)), 2.0);
            vec2 rUV = fract(fract(uv) + vec2(1.0, 1.0));
            return mix(rUV, vec2(1.0) - rUV, mUV);
        }

        vec2 repeatUV(vec2 uv)
        {
            return fract(fract(uv) + vec2(1.0, 1.0));
        }

        vec2 clampUV(vec2 uv)
        {
            return clamp(uv, vec2(0.0), vec2(1.0));
        }

        void main()
        {
            vec4 color = texture2D(uTexture0, vTexCoord);
            gl_FragColor = mix(color * uColor, uColor * color.a, step(0.5, uType));
        }
        ]],
    
    fs_discard = [[
            precision highp float;
            varying vec2 vTexCoord;
    
            uniform sampler2D uTexture0;
            uniform vec4 uColor;
            uniform float uType;
            uniform float uClipEpsilon;
    
            vec2 mirrorRepeatUV(vec2 uv)
            {
                vec2 mUV = mod(abs(floor(uv)), 2.0);
                vec2 rUV = fract(fract(uv) + vec2(1.0, 1.0));
                return mix(rUV, vec2(1.0) - rUV, mUV);
            }
    
            vec2 repeatUV(vec2 uv)
            {
                return fract(fract(uv) + vec2(1.0, 1.0));
            }
    
            vec2 clampUV(vec2 uv)
            {
                return clamp(uv, vec2(0.0), vec2(1.0));
            }
    
            void main()
            {
                vec4 color = texture2D(uTexture0, vTexCoord);
                if(length(color) < uClipEpsilon)  discard;
                gl_FragColor = mix(color * uColor, uColor * color.a, step(0.5, uType));
            }
            ]],

    fs_antialias = [[
        //#extension GL_OES_standard_derivatives : enable
        precision highp float;
        varying vec2 vTexCoord;
        uniform sampler2D uTexture0;
        uniform sampler2D uTexture1;
        uniform vec4 uColor;
        uniform float uType;
        uniform float uClipEpsilon;
        uniform vec2 uResolution;

        void main()
        {
            vec4 color = texture2D(uTexture0, vTexCoord);
            vec4 bg = texture2D(uTexture1, gl_FragCoord.xy / uResolution);

            //vec2 uStepRange = abs(fwidth(vTexCoord));
            vec2 uStepRange = vec2(2.0) / uResolution;
            float lerpU = smoothstep(0.0, uStepRange.x, vTexCoord.x) - smoothstep(1.0 - uStepRange.x, 1.0, vTexCoord.x);
            float lerpV = smoothstep(0.0, uStepRange.y, vTexCoord.y) - smoothstep(1.0 - uStepRange.y, 1.0, vTexCoord.y);
            
            if(length(color) < uClipEpsilon)
                discard;

            vec4 color1 = mix(uColor * color, uColor * color.a, step(0.5, uType));
            gl_FragColor = vec4(mix(bg.rgb, color1.rgb, lerpU * lerpV), color1.a);
        }
    ]],
    animatePass = nil,
    simplePass = nil,
    fillPass = nil,
    clipPass = nil,
    antialiasPass = nil,
    color = Vec4f.new(1.0, 1.0, 1.0, 1.0),
    tileX = 1,
    tileY = 1,
    animFPS = 1,
    timestamp = 0,
    clipEpsilon = 0.02
}

function TextureRender:initParams(context, filter)
    filter:insertColorParam("Color", self.color)
    filter:insertIntParam("TileX", 1, 20, self.tileX)
	filter:insertIntParam("TileY", 1, 20, self.tileY)
	filter:insertIntParam("FPS", 1, 60, self.animFPS)
    
    filter:insertEnumParam("RenderType", 0, { "Image", "Color" })
end

function TextureRender:initRenderer(context, filter)
    OF_LOGI(TAG, "call initParams")
    if self.animatePass == nil then
        self.animatePass = context:createCustomShaderPass(self.vs, self.fs_animate)
    end
    if self.simplePass == nil then
        self.simplePass = context:createCustomShaderPass(self.vs, self.fs_simple)
    end
    if self.antialiasPass == nil then
        self.antialiasPass = context:createCustomShaderPass(self.vs_antialias, self.fs_antialias)
    end
    if self.clipPass == nil then
        self.clipPass = context:createCustomShaderPass(self.vs, self.fs_discard)
    end
    return OF_Result_Success
end

function TextureRender:onApplyParams(context, filter)
    self.color = filter:colorParam("Color")
    self.tileX = filter:intParam("TileX")
    self.tileY = filter:intParam("TileY")
    self.animFPS = filter:intParam("FPS")
    self.renderType= filter:enumParam("RenderType")
    return OF_Result_Success
end

function TextureRender:teardown(context, filter)
    OF_LOGI(TAG, "call teardownRenderer")
    if self.animatePass then
        context:destroyCustomShaderPass(self.animatePass)
        self.animatePass = nil
    end
    if self.simplePass then
        context:destroyCustomShaderPass(self.simplePass)
        self.simplePass = nil
    end
    if self.antialiasPass then
        context:destroyCustomShaderPass(self.antialiasPass)
        self.antialiasPass = nil
    end
    if self.clipPass then
        context:destroyCustomShaderPass(self.clipPass)
        self.clipPass = nil
    end
    return OF_Result_Success
end

function TextureRender:setColor(color)
    self.color = color
end

function TextureRender:setOpacity(opacity)
    self.color.w = opacity
end

function TextureRender:setAnimationData(tileX, tileY, animFPS, timestamp)
    self.tileX = tileX
    self.tileY = tileY
    self.animFPS = animFPS
    self.timestamp = timestamp
end

function TextureRender:drawAntiAlias(context, baseTex, inTex, outTex, texMat)
    if baseTex == nil then
        return self:draw(context, inTex, outTex, texMat)
    end
    context:bindFBO(outTex)
    context:setViewport(0, 0, outTex.width, outTex.height)

    local pass = self.antialiasPass
    pass:use()
    pass:setUniformMatrix4fv("uMVP", 1, 0, texMat.x)
    pass:setUniformTexture("uTexture0", 0, inTex.textureID, TEXTURE_2D)
    pass:setUniform4f("uColor", self.color.x, self.color.y, self.color.z, self.color.w)
    pass:setUniform2f("uResolution", outTex.width, outTex.height)
    pass:setUniformTexture("uTexture1", 1, baseTex.textureID, TEXTURE_2D) 
    pass:setUniform1f("uType", self.renderType)
    pass:setUniform1f("uClipEpsilon", self.clipEpsilon)

    local quadRender = context:sharedQuadRender()
    quadRender:draw(pass, false)
end

function TextureRender:draw(context, inTex, outTex, texMat, discard)
    context:bindFBO(outTex)
    context:setViewport(0, 0, outTex.width, outTex.height)

    local pass = self.simplePass
    if discard ~= nil and discard ~= false then
        pass = self.clipPass
    end
    pass:use()
    pass:setUniformTexture("uTexture0", 0, inTex.textureID, TEXTURE_2D)
    pass:setUniform4f("uColor", self.color.x, self.color.y, self.color.z, self.color.w)
    pass:setUniformMatrix4fv("uMVP", 1, 0, texMat.x)
    pass:setUniform1f("uType", self.renderType)
    if discard ~= nil then
        pass:setUniform1f("uClipEpsilon", self.clipEpsilon)
    end

    local quadRender = context:sharedQuadRender()
    quadRender:draw(pass, false)
end

function TextureRender:drawWithAnimation(context, inTex, outTex, texMat)
    context:bindFBO(outTex)
    context:setViewport(0, 0, outTex.width, outTex.height)

    self.animatePass:use()
    self.animatePass:setUniformTexture("uTexture0", 0, inTex.textureID, TEXTURE_2D)
    self.animatePass:setUniform4f("uColor", self.color.x, self.color.y, self.color.z, self.color.w)
    self.animatePass:setUniformMatrix4fv("uMVP", 1, 0, texMat.x)
    self.animatePass:setUniform1f("uTileX", self.tileX)
    self.animatePass:setUniform1f("uTileY", self.tileY)
    self.animatePass:setUniform1f("uAnimFPS", self.animFPS)
    self.animatePass:setUniform1f("uTimestamp", self.timestamp)

    local quadRender = context:sharedQuadRender()
    quadRender:draw(self.animatePass, false)
end

return TextureRender