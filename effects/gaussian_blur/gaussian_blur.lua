local TAG = "OrangeFilter-GaussianBlurFilter"

local BlurRender = require "common.gaussian_blur"

function initParams(context, filter)
    OF_LOGI(TAG, "call GaussianBlurFilter initParams")

    BlurRender:initParams(context, filter)
    return OF_Result_Success
end

function onApplyParams(context, filter)
    BlurRender:onApplyParams(context, filter)
    return OF_Result_Success
end

function initRenderer(context, filter)
    OF_LOGI(TAG, "call GaussianBlurFilter initRenderer")
    
    BlurRender:initRenderer(context, filter)
    return OF_Result_Success
end

function teardownRenderer(context, filter)
    OF_LOGI(TAG, "call GaussianBlurFilter teardownRenderer")
    BlurRender:teardown(context, filter)
    return OF_Result_Success
end

function applyFrame(context, filter, frameData, inTexArray, outTexArray)
    BlurRender:draw(context, inTexArray[1], outTexArray[1])

    -- debug tex
	if outTexArray[2] ~= nil then
		context:copyTexture(inTexArray[1], outTexArray[2])
	end 

    return OF_Result_Success
end

function requiredFrameData(context, game)
    return {
        OF_RequiredFrameData_None
    }
end

function readObject(context, filter, archiveIn)
    OF_LOGI(TAG, "call readObject")
    return OF_Result_Success
end

function writeObject(context, filter, archiveOut)
    OF_LOGI(TAG, "call writeObject")
    return OF_Result_Success
end
