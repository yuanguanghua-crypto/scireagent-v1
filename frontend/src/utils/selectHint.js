/**
 * 「只显示了一部分」的提示文案 —— A-206（2026-11-18 / S4）。
 *
 * ## 为什么要有这个函数
 * 产品编辑页的四个知识实体下拉（Goals / Applications / Methods / Protocols）
 * 全都是**服务端分页 + 静默截断**：首屏或搜索只取 50~500 条，其余不显示也不提示。
 * 用户于是得出"库里没有这个实体"的结论，转而去新建一条 —— 而那条很可能已经存在
 * （Method 侧就会直接撞 409 同名）。截断必须说出来。
 *
 * ## 两种措辞为什么不同
 * · 未搜索（首屏预加载）：用户还没输入过任何东西，要说清"其余的需要搜索才能出来"；
 * · 已搜索（命中被截断）：用户的查询本身命中太多，要说清"继续输入缩小范围"。
 * 混用会给出错误指令（对没输入过的人说"继续输入"没有意义）。
 *
 * `total == null` 表示服务端没回分页 meta（数组直出）——此时**不猜数字**、不提示。
 */
export function selectTruncationHint({ searched, shown, total }) {
  if (total == null || total <= shown) return ''
  return searched
    ? `Showing first ${shown} of ${total} matches — keep typing to narrow down.`
    : `Only the first ${shown} of ${total} are preloaded — type to search the rest.`
}
