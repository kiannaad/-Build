window.__ModuleLoader__.load({
  id: 'dsh-memory-galaxy',
  factory(require) {
    const React = require('react');
    const h = React.createElement;
    const KIND = 'memory-galaxy';
    const TAB_ID = 'dsh-memory-galaxy';
    const SRC = 'http://127.0.0.1:9882/galaxy-lab.html?embed=1';

    function GalaxyBody() {
      return h('iframe', {
        title: '记忆星河',
        src: SRC,
        allow: 'fullscreen',
        style: {
          display: 'block',
          width: '100%',
          height: '100%',
          border: 0,
          background: '#03050c',
        },
      });
    }

    return {
      inject: ['slots', 'sidebarRight', 'sidebarRightTabs'],
      apply(ctx) {
        ctx.effect(() => ctx.sidebarRightTabs.register({
          id: TAB_ID,
          kind: KIND,
          title: () => '记忆星河',
          guide: [{
            id: 'memory-galaxy',
            order: 40,
            title: () => '记忆星河',
            description: () => '大肥鱼的 3D 记忆星图（Bloom 版）',
          }],
        }), 'memory-galaxy: tab type');

        ctx.slots.inject('sidebar.right.pane.tab', () => ctx.slots.register({
          name: 'sidebar.right.pane.tab',
          key: TAB_ID,
        }, GalaxyBody));

        ctx.slots.inject('conversation.session.header.utilities', () => ctx.slots.register({
          name: 'conversation.session.header.utilities',
          id: 'memory-galaxy-open',
          order: 20,
        }, () => h('button', {
          type: 'button',
          title: '打开记忆星河',
          'aria-label': '打开记忆星河',
          onClick: () => ctx.sidebarRight.openTab(KIND, { destination: 'sidebar' }),
          style: {
            height: 26,
            padding: '0 9px',
            border: '1px solid var(--dsw-alias-border-secondary, rgba(127,127,127,.28))',
            borderRadius: 999,
            background: 'transparent',
            color: 'var(--dsw-alias-text-secondary, #8a9bb8)',
            cursor: 'pointer',
            fontSize: 11,
            lineHeight: '24px',
            whiteSpace: 'nowrap',
          },
        }, '✦ 记忆星河')));
      },
    };
  },
});
