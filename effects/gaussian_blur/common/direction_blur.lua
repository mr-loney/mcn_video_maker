local TAG = "DirectBlurRender"
local directBlurRender = {
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
    fs_blur = [[
        precision highp float;
    
        varying vec2 vTexCoord;

        uniform float uStrength;
        uniform float uDirection;
        uniform int   nSamples;
        uniform sampler2D uTexture0;
        
        const int INT_MAX = 9999;

        void main()
        {
            vec2 uv = vTexCoord;
            float originA = texture2D(uTexture0, vTexCoord).a;
            vec4 color = vec4(0.0);
            vec2 dirVec = vec2(cos(uDirection), sin(uDirection));
            vec2 stepVal = dirVec * 2.0 * uStrength / float(nSamples);
            for(int i = 0; i < INT_MAX; i++)
            {
                if(i >= nSamples) break;
                vec2 offsetUV = uv + stepVal * float(i - nSamples / 2);
                //color += texture2D(uTexture0, offsetUV).rgb;
                //color += texture2D(uTexture0, offsetUV) * step(0.0, offsetUV.x) * step(0.0, offsetUV.y) * step(offsetUV.x, 1.0) * step(offsetUV.y, 1.0);
                color += texture2D(uTexture0, offsetUV);
            }

            gl_FragColor = color / float(nSamples);
        }
        ]],
    
    _blurPass = nil,
    _blurStrength = 0.5,
    _blurDirection = 0,
    _blurIterCount = 2
}

function directBlurRender:initParams(context, filter)
    filter:insertFloatParam("BlurStrength", 0.0, 1.0, self._blurStrength)
    filter:insertIntParam("BlurDirection", -180, 180, self._blurDirection)
	filter:insertIntParam("BlurStep", 1, 30, self._blurIterCount)
end

function directBlurRender:initRenderer(context, filter)
    OF_LOGI(TAG, "call directBlurRender initRenderer")
    self._blurPass = context:createCustomShaderPass(self.vs, self.fs_blur)
    return OF_Result_Success
end

function directBlurRender:teardown(context, filter)
    OF_LOGI(TAG, "call  directBlurRender teardownRenderer")
    if self._blurPass then
        context:destroyCustomShaderPass(self._blurPass)
        self._blurPass = nil
    end
    return OF_Result_Success
end

function directBlurRender:onApplyParams(context, filter)
    self._blurStrength = filter:floatParam("BlurStrength")
    self._blurDirection = filter:intParam("BlurDirection")
    self._blurIterCount = filter:intParam("BlurStep")

    return OF_Result_Success
end

function directBlurRender:draw(context, inTex, outTex)
    local width = outTex.width
    local height = outTex.height

    local render = context:sharedQuadRender()

    context:bindFBO(outTex)
    context:setViewport(0, 0, width, height)

    self._blurPass:use()
    self._blurPass:setUniformMatrix4fv("uMVP", 1, 0, Matrix4f.new().x)
    self._blurPass:setUniformTexture("uTexture0", 0, inTex.textureID, GL_TEXTURE_2D)
    self._blurPass:setUniform1f("uStrength", self._blurStrength / 10.0)
    self._blurPass:setUniform1f("uDirection", math.rad(self._blurDirection))
    self._blurPass:setUniform1i("nSamples", self._blurIterCount)

    render:draw(self._blurPass, false)

    return OF_Result_Success
end


return directBlurRender