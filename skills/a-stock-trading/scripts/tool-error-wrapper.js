/**
 * 工具错误包裹器 (DeerFlow ToolErrorHandlingMiddleware 移植)
 * 
 * 所有工具调用被 try/catch 包裹，错误返回为结构化消息而非抛异常。
 * Agent 看到错误后继续运行，不中断 session。
 * 
 * 移植自: bytedance/deer-flow → tool_error_handling_middleware.py
 */

/**
 * 安全调用工具函数
 * @param {string} toolName - 工具名称
 * @param {Function} toolFunc - 工具函数
 * @param {Object} args - 参数
 * @returns {Promise<any>} 工具结果或错误消息
 */
async function safeToolCall(toolName, toolFunc, args = {}) {
  try {
    const result = await toolFunc(args);
    return result;
  } catch (err) {
    const detail = (err.message || String(err)).slice(0, 500);
    console.error('[ToolError] ' + toolName + ' failed: ' + detail);
    return {
      _error: true,
      _toolName: toolName,
      content: '⚠️ ' + toolName + ' 执行出错：' + detail + '。请用可用数据继续分析。'
    };
  }
}

/**
 * 批量安全调用工具
 * @param {Array} calls - [{name, func, args}]
 * @returns {Promise<Array>}
 */
async function safeBatchToolCalls(calls) {
  const results = [];
  for (const { name, func, args } of calls) {
    results.push(await safeToolCall(name, func, args));
  }
  return results;
}

/**
 * 为整个工具对象添加安全包裹
 * @param {Object} toolModule - 包含多个工具方法的对象
 * @returns {Object} 包裹后的工具对象
 */
function wrapToolModule(toolModule) {
  const wrapped = {};
  for (const [name, func] of Object.entries(toolModule)) {
    if (typeof func === 'function') {
      wrapped[name] = async (args) => safeToolCall(name, func, args);
    } else {
      wrapped[name] = func;
    }
  }
  return wrapped;
}

module.exports = {
  safeToolCall,
  safeBatchToolCalls,
  wrapToolModule
};
