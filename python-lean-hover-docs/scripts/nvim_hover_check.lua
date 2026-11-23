-- nvim_hover_check.lua —— headless 下模拟「按 K」，把悬停浮窗内容原样打印。
-- 环境变量：HOVER_LINE / HOVER_COL（1-based）、HOVER_WAIT_MS（默认 18000，
-- 等 LSP 就绪用，慢机器可调大）。
local line = tonumber(os.getenv('HOVER_LINE') or '1')
local col = tonumber(os.getenv('HOVER_COL') or '1')
local wait_ms = tonumber(os.getenv('HOVER_WAIT_MS') or '18000')

vim.defer_fn(function()
  vim.api.nvim_win_set_cursor(0, { line, col - 1 })
  vim.lsp.buf.hover()
  vim.defer_fn(function()
    local found = false
    for _, w in ipairs(vim.api.nvim_list_wins()) do
      local cfg = vim.api.nvim_win_get_config(w)
      if cfg.relative ~= '' then
        local buf = vim.api.nvim_win_get_buf(w)
        local text = table.concat(vim.api.nvim_buf_get_lines(buf, 0, -1, false), '\n')
        if text ~= '' then
          print('===== NVIM HOVER (K) =====')
          print(text)
          found = true
        end
      end
    end
    if not found then
      print('===== NVIM HOVER：未找到浮窗（LSP 未就绪或该处无悬停） =====')
    end
    vim.cmd('qa!')
  end, 9000)
end, wait_ms)
