local TAG = "RadialBlurRender"

BLUR_TYPE_ROTATE = 0
BLUR_TYPE_SCALE  = 1

local RadialBlurRender = {
    vs = [[
        precision highp float;
        attribute vec4 aPosition;
        attribute vec4 aTextureCoord;
        varying vec2 vTexCoord; 
         
        void main()
        {
            gl_Position = aPosition; 
            vTexCoord = aTextureCoord.xy;
        }
    ]],
    
    blur_rotate_fs = [[
        precision highp float;
    
        varying vec2 vTexCoord;

        uniform sampler2D uTexture0;
        uniform float uBlurStrength;
        uniform vec2 uTexSize;
        uniform vec2 uCenter;
        uniform int nSamples;

        const int INT_MAX = 9999;

        mat2 rotate2d(float radian) {
            vec2 sc = vec2(sin(radian), cos(radian));
            return mat2( sc.y, -sc.x, sc.x, sc.y );
        }

        void main() {
            float originA = texture2D(uTexture0, vTexCoord).a;
            vec2 uv = vTexCoord.xy * uTexSize;
            vec2 center = uCenter * uTexSize;
            vec4 color = vec4(0.0);
            float precompute = uBlurStrength * (1.0 / float(nSamples));
            for (int i = 0; i < INT_MAX; i ++)
            {
                if(i >= nSamples) break;
                vec2 uvR = uv - center;
                uvR *= rotate2d(precompute * float((i - nSamples / 2)));   
                uvR += center;
                vec2 offsetUV = uvR / uTexSize;
                vec4 sample = texture2D(uTexture0, offsetUV);
                //color += texture2D(uTexture0, offsetUV) * step(0.0, offsetUV.x) * step(0.0, offsetUV.y) * step(offsetUV.x, 1.0) * step(offsetUV.y, 1.0);
                color += texture2D(uTexture0, offsetUV);
            }   

            gl_FragColor = color / float(nSamples);
        }
    ]],

    blur_scale_fs = [[
        precision highp float;
    
        varying vec2 vTexCoord;

        uniform sampler2D uTexture0;
        uniform float uBlurStrength;
        uniform float rate;
        uniform float power;
        uniform vec2 uCenter;
        uniform int nSamples;
        
        const int INT_MAX = 9999;

        float fit(float val,float inmin,float inmax,float outmin,float outmax)
        {
            return clamp((outmin + (val - inmin) * (outmax - outmin) / (inmax - inmin)),min(outmin,outmax),max(outmin,outmax));
        }
    
        void main()
        {
            vec2 uv = vTexCoord - uCenter;

            float precompute = uBlurStrength * (1.0 / float(nSamples));
            //precompute *= pow(smoothstep(0.,0.4,t),2.)*pow(smoothstep(1.,0.4,t),2.);

            float originA = texture2D(uTexture0, vTexCoord).a;
            vec4 color = vec4(0.0);
            for(int i = 0; i < INT_MAX; i++)
            {
                if(i >= nSamples) break;

                vec2 offsetUV = vTexCoord - uv * (float(i) * precompute);
                color += texture2D(uTexture0, offsetUV);
                offsetUV = vTexCoord + uv *  (float(i)* precompute);
                color += texture2D(uTexture0, offsetUV);
            }

            gl_FragColor = color / float(nSamples * 2);
        }
    ]],

    _blurScalePass = nil,
    _blurRotatePass = nil,
    _blurType = BLUR_TYPE_ROTATE,
    _blurIterCount = 30,
    _time = 0.0,
    _blurStrength = 0.2,
    -- _rate = 0.5,
    -- _pow = 1.0,
    _cx = 0.5,
    _cy = 0.5
}

function RadialBlurRender:initRenderer(context, filter)
    OF_LOGI("RadialBlurRender", "call RadialBlurRender:initRenderer")

    self._blurScalePass = context:createCustomShaderPass(self.vs, self.blur_scale_fs)
    self._blurRotatePass = context:createCustomShaderPass(self.vs, self.blur_rotate_fs)

    return OF_Result_Success
end

function RadialBlurRender:teardown(context, filter)
    OF_LOGI("RadialBlurRender", "call RadialBlurRender:teardown")

    context:destroyCustomShaderPass(self._blurScalePass)
    context:destroyCustomShaderPass(self._blurRotatePass)
    self._blurScalePass = nil
    self._blurRotatePass = nil
	
    return OF_Result_Success
end

function RadialBlurRender:initParams(context, filter)
	--filter:insertFloatParam("Time", 0.0, 1.0, 0.4)
	-- filter:insertFloatParam("Pow", 0.0, 2.0, 1.0)
	-- filter:insertFloatParam("Rate", 0.0, 10.0, 1.0)
	filter:insertFloatParam("BlurStrength", 0.0, 1.0, 0.3)
    -- filter:insertIntParam("BlurStep", 1, 100, self._blurIterCount)
    filter:insertEnumParam("BlurType", BLUR_TYPE_ROTATE, { "Rotate", "Scale"})
	filter:insertFloatParam("CenterX", 0.0, 1.0, 0.5)
	filter:insertFloatParam("CenterY", 0.0, 1.0, 0.5)

    return OF_Result_Success
end

function RadialBlurRender:onApplyParams(context, filter, dirtyTable)
	--self._time = filter:floatParam("Time")
	-- self._pow = filter:floatParam("Pow")
	self._blurStrength = filter:floatParam("BlurStrength")

	-- self._rate = filter:floatParam("Rate")
	self._cx = filter:floatParam("CenterX")
	self._cy = filter:floatParam("CenterY")
	self._time = filter:timestamp()
    self._blurType = filter:enumParam("BlurType")
    return OF_Result_Success
end

function RadialBlurRender:draw(context, inTex, outTex)
    local width = outTex.width
    local height = outTex.height

    local render = context:sharedQuadRender()

    local pass = self._blurScalePass
    if self._blurType == BLUR_TYPE_ROTATE then
        pass = self._blurRotatePass
    end

    context:bindFBO(outTex)
    context:setViewport(0, 0, width, height)
    pass:use()
    pass:setUniformTexture("uTexture0", 0, inTex.textureID, GL_TEXTURE_2D)
    -- pass:setUniform1f("iTime", self._time)
    if self._blurType == BLUR_TYPE_SCALE then
        -- pass:setUniform1f("rate", self._rate)
        -- pass:setUniform1f("power", self._pow)
        pass:setUniform1f("uBlurStrength", self._blurStrength / 2)
        self._blurIterCount = math.max(self._blurStrength / 10 * math.min(width, height), 1)
    else
        pass:setUniform2f("uTexSize", inTex.width, inTex.height)
        pass:setUniform1f("uBlurStrength", self._blurStrength * 2)
        self._blurIterCount = math.max(self._blurStrength / 5 * math.min(width, height), 1)
    end
    pass:setUniform2f("uCenter", self._cx, self._cy)
    pass:setUniform1i("nSamples", self._blurIterCount)

    render:draw(pass, false)

    return OF_Result_Success
end

return RadialBlurRender
