local TAG = "GaussBlurRender"
local gaussBlurRender = {
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
    fs_gauss_blur = [[
        precision highp float;
        varying vec2 vTexCoord;
        uniform sampler2D uTexture;
        uniform vec2 uOnePixel;
        uniform float uKernel[50];
        uniform int uKernelSize;
        
        const int INT_MAX = 9999;
        
        void main()
        {
            vec4 color = texture2D(uTexture, vTexCoord) * uKernel[0];
            for (int i = 1; i < INT_MAX; i++)
            {
                if(i >= uKernelSize) break;
                vec2 pixelOffset = uOnePixel * vec2(i);
                color += texture2D(uTexture, vTexCoord + pixelOffset) * uKernel[i];
                color += texture2D(uTexture, vTexCoord - pixelOffset) * uKernel[i];
            }
            gl_FragColor = color;
        }
        ]],
    
    blurPass = nil,
    blurKernel = FloatArray.new(50),
    blurStrength = 0.5,
    blurKernelSize = 3,
    blurHorizontal = true,
    blurVertical = true,
    blurIterCount = 2
}

function gaussBlurRender:initParams(context, filter)
    filter:insertFloatParam("BlurStrength", 0.0, 1.0, self.blurStrength)
	filter:insertIntParam("BlurStep", 1, 10, self.blurIterCount)
    filter:insertEnumParam("BlurDirection", 0, { "HorizontalAndVertical", "Horizontal", "Vertical"})
end

function gaussBlurRender:initRenderer(context, filter)
    OF_LOGI(TAG, "call gaussBlurRender initRenderer")
    self.blurPass = context:createCustomShaderPass(self.vs, self.fs_gauss_blur)
    return OF_Result_Success
end

function gaussBlurRender:teardown(context, filter)
    OF_LOGI(TAG, "call gaussBlurRender teardownRenderer")
    if self.blurPass then
        context:destroyCustomShaderPass(self.blurPass)
        self.blurPass = nil
    end
    return OF_Result_Success
end

function gaussBlurRender:onApplyParams(context, filter)
    self.blurKernekSize = math.ceil(filter:floatParam("BlurStrength") * 48)
    self.blurIterCount = filter:floatParam("BlurStrength") * 10;
    self.blurStrength = filter:floatParam("BlurStrength")
    if filter:enumParam("BlurDirection") == 0 then
        self.blurVertical = true
        self.blurHorizontal = true
    elseif filter:enumParam("BlurDirection") == 1 then
        self.blurVertical = false
        self.blurHorizontal = true
    else
        self.blurVertical = true
        self.blurHorizontal = false
    end

    self.makeGaussKernel(self, 3, self.blurKernekSize)
    return OF_Result_Success
end

function gaussBlurRender:makeGaussKernel(sigma, kernel_size)
    local sqrt_sigma_pi2  = math.sqrt(math.pi * 2.0) * sigma
    local s2 = 2.0 * sigma * sigma
    local sum = 0.0
    for i = 0, kernel_size do
        local value = math.exp(-(i * i) / s2) / sqrt_sigma_pi2
        self.blurKernel:set(i, value)
        if i == 0 then
            sum = sum + value
        else
            sum = sum + value * 2
        end
    end

    -- normalize
    for i = 0, kernel_size do
        self.blurKernel:set(i, self.blurKernel:get(i) / sum)
        --print(i, self.blurKernel:get(i))
    end
    self.blurKernekSize = kernel_size + 1
end

function gaussBlurRender:setGaussStrength(value)
    self.blurKernekSize = math.ceil(value * 48)
    self.blurStrength = value
    
    self.makeGaussKernel(self, 3, self.blurKernekSize)
end

function gaussBlurRender:setGaussIterCount(iterNum)
    self.blurIterCount = iterNum
end

function gaussBlurRender:smoothstep(edge0, edge1, x) 
    x = (x - edge0) / (edge1 - edge0)
    return x * x * (3 - 2 * x)
end

function gaussBlurRender:draw(context, inTex, outTex)
    local width  = inTex.width * (1.0 - 0.85 * self:smoothstep(0.0, 1.0, self.blurStrength))
    local height = inTex.height * (1.0 - 0.85 * self:smoothstep(0.0, 1.0, self.blurStrength))
    local cache_tex = context:getTexture(width, height)
    local out_tex = context:getTexture(width, height)
    local quad_render = context:sharedQuadRender()

    context:setViewport(0, 0, width, height)
    context:setBlend(false)
    self.blurPass:use()
    self.blurPass:setUniformMatrix4fv("uMVP", 1, 0, Matrix4f.new().x)
    self.blurPass:setUniform1fv("uKernel", self.blurKernel:size(), self.blurKernel)
    self.blurPass:setUniform1i("uKernelSize", self.blurKernekSize)

    local function doBlur(texture)
        context:bindFBO(cache_tex:toOFTexture())
        self.blurPass:setUniform2f("uOnePixel", (self.blurHorizontal and {1.0 / width} or {0.0})[1], 0.0)
        self.blurPass:setUniformTexture("uTexture", 0, texture.textureID, TEXTURE_2D)
    
        quad_render:draw(self.blurPass, false)

        context:bindFBO(out_tex:toOFTexture())
        self.blurPass:setUniform2f("uOnePixel", 0.0, (self.blurVertical and {1.0 / height} or {0.0})[1])
        self.blurPass:setUniformTexture("uTexture", 0, cache_tex:textureID(), TEXTURE_2D)
    
        quad_render:draw(self.blurPass, false)
    end

    doBlur(inTex)

    for i = 1, self.blurIterCount-1 do
        doBlur(out_tex:toOFTexture())
    end

    context:copyTexture(out_tex:toOFTexture(), outTex)

    context:releaseTexture(cache_tex)
    context:releaseTexture(out_tex)
end


return gaussBlurRender