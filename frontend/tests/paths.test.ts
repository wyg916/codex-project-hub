import { compactLocalPath } from '../src/utils/paths'

describe('路径隐私显示', () => {
  it('只显示 Windows 和 POSIX 路径的末级目录', () => {
    expect(compactLocalPath('C:\\Users\\demo\\Project Alpha')).toBe('…/Project Alpha')
    expect(compactLocalPath('/home/demo/project-beta/')).toBe('…/project-beta')
  })

  it('缺失路径时使用安全占位符', () => {
    expect(compactLocalPath(undefined)).toBe('未检出')
    expect(compactLocalPath('', '无工作区')).toBe('无工作区')
  })
})
