/**
 * MockAPI - 模拟后端 API 层
 * 
 * 覆盖家属端前端所有需要用到的 API 接口。
 * 返回符合真实 API 契约结构的模拟数据。
 * 所有数据为中文，贴合 AD 照护场景。
 */

const MockAPI = {
  // ================================================================
  // 设备绑定与配置
  // ================================================================

  /**
   * 扫码绑定设备
   * @param {string} deviceCode - 6 位设备码
   * @returns {Promise<Object>} { patient_id, is_new, role }
   */
  scanBinding: (deviceCode) => {
    console.log(`[MockAPI] scanBinding: deviceCode=${deviceCode}`);
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          patient_id: '550e8400-e29b-41d4-a716-446655440001',
          device_code: deviceCode || 'A1B2C3',
          is_new: true,
          role: 'admin',
          patient_name: '张伯伯',
          display_name: '张伯伯'
        });
      }, 500);
    });
  },

  /**
   * 完成初始化配置（仅 admin）
   * @param {Object} config - { era, region, language, persona_name }
   * @returns {Promise<Object>}
   */
  completeConfig: (config) => {
    console.log(`[MockAPI] completeConfig:`, config);
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          success: true,
          patient_id: '550e8400-e29b-41d4-a716-446655440001',
          config: {
            era: config.era || '1980s',
            region: config.region || { country: 'CN', province: '广东', city: '广州' },
            language: config.language || 'zh-CN',
            persona_name: config.persona_name || '强叔',
            timezone: 'Asia/Shanghai'
          }
        });
      }, 800);
    });
  },

  /**
   * 获取患者配置
   * @param {string} patientId
   * @returns {Promise<Object>}
   */
  getPatientConfig: (patientId) => {
    console.log(`[MockAPI] getPatientConfig: patientId=${patientId}`);
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          patient_id: patientId || '550e8400-e29b-41d4-a716-446655440001',
          era: '1980s',
          region: { country: 'CN', province: '广东', city: '广州' },
          language: 'zh-CN',
          timezone: 'Asia/Shanghai',
          persona_name: '强叔',
          privacy_consent: { status: 'signed', policy_version: 'v1.0', confirmed_at: '2026-09-01T10:00:00Z' }
        });
      }, 300);
    });
  },

  // ================================================================
  // 知情同意
  // ================================================================

  /**
   * 签署知情同意
   * @param {Object} data - { caregiver_name, patient_id }
   * @returns {Promise<Object>} { id, signed_at }
   */
  signConsent: (data) => {
    console.log(`[MockAPI] signConsent:`, data);
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          id: '660e8400-e29b-41d4-a716-446655440002',
          caregiver_id: '770e8400-e29b-41d4-a716-446655440003',
          patient_id: data.patient_id || '550e8400-e29b-41d4-a716-446655440001',
          consent_version: 'v1.0',
          content_hash: 'a1b2c3d4e5f6...',
          signed_at: new Date().toISOString()
        });
      }, 600);
    });
  },

  /**
   * 查询知情同意记录
   * @param {string} patientId
   * @returns {Promise<Array>}
   */
  getConsents: (patientId) => {
    console.log(`[MockAPI] getConsents: patientId=${patientId}`);
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve([
          {
            id: '660e8400-e29b-41d4-a716-446655440002',
            caregiver_id: '770e8400-e29b-41d4-a716-446655440003',
            caregiver_name: '李娟',
            consent_version: 'v1.0',
            signed_at: '2026-09-01T10:00:00Z'
          }
        ]);
      }, 300);
    });
  },

  // ================================================================
  // 记忆管理
  // ================================================================

  /**
   * 提交记忆（语音/文字/照片）
   * @param {Object} data - { patient_id, raw_text, photo?, audio? }
   * @returns {Promise<Object>} { id, entities, confidence, sync_status }
   */
  submitMemory: (data) => {
    console.log(`[MockAPI] submitMemory:`, data);
    return new Promise((resolve) => {
      // 模拟后端处理延迟 1-2s
      const delay = 1000 + Math.random() * 1000;
      setTimeout(() => {
        // 根据输入文本模拟实体抽取
        const entities = mockEntityExtraction(data.raw_text || '');
        resolve({
          id: '880e8400-e29b-41d4-a716-' + Date.now().toString(16).padStart(12, '0'),
          patient_id: data.patient_id || '550e8400-e29b-41d4-a716-446655440001',
          raw_text: data.raw_text || '',
          photo_url: data.photo_url || null,
          entities: entities,
          confidence: entities.confidence || 0.82,
          sync_status: 'synced',
          created_at: new Date().toISOString()
        });
      }, delay);
    });
  },

  /**
   * 编辑记忆实体
   * @param {string} id - 记忆 ID
   * @param {Object} entities - 更新后的实体
   * @returns {Promise<Object>}
   */
  updateMemory: (id, entities) => {
    console.log(`[MockAPI] updateMemory: id=${id}`, entities);
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          id: id,
          entities: entities,
          updated_at: new Date().toISOString(),
          success: true
        });
      }, 400);
    });
  },

  /**
   * 删除记忆
   * @param {string} id
   * @returns {Promise<Object>} { success }
   */
  deleteMemory: (id) => {
    console.log(`[MockAPI] deleteMemory: id=${id}`);
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({ success: true, id: id });
      }, 300);
    });
  },

  /**
   * 查询记忆列表
   * @param {Object} params - { patient_id, tag?, page?, page_size? }
   * @returns {Promise<Array>}
   */
  getMemories: (params) => {
    console.log(`[MockAPI] getMemories:`, params);
    return new Promise((resolve) => {
      setTimeout(() => {
        const tag = params?.tag || 'all';
        let memories = mockMemoriesData();
        if (tag !== 'all') {
          memories = memories.filter(m => {
            const entities = m.entities || {};
            const tags = [];
            if (entities.era) tags.push('年代');
            if (entities.location && entities.location.length) tags.push('地点');
            if (entities.event) tags.push('事件');
            if (entities.preference && entities.preference.length) tags.push('喜好');
            return tags.includes(tag);
          });
        }
        resolve(memories);
      }, 500);
    });
  },

  // ================================================================
  // 照片管理
  // ================================================================

  /**
   * 上传照片
   * @param {File|Blob} photo - 照片文件
   * @param {Object} meta - { patient_id, persona_name?, relation? }
   * @returns {Promise<Object>}
   */
  uploadPhoto: (photo, meta) => {
    console.log(`[MockAPI] uploadPhoto:`, meta);
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          id: '990e8400-e29b-41d4-a716-' + Date.now().toString(16).padStart(12, '0'),
          patient_id: meta.patient_id || '550e8400-e29b-41d4-a716-446655440001',
          object_url: 'https://minio.example.com/memories/photo_001.jpg',
          thumbnail_url: 'https://minio.example.com/memories/thumb_001.jpg',
          persona_name: meta.persona_name || null,
          persona_relation: meta.relation || null,
          created_at: new Date().toISOString()
        });
      }, 800);
    });
  },

  /**
   * 查询照片列表
   * @param {Object} params - { patient_id }
   * @returns {Promise<Array>}
   */
  getPhotos: (params) => {
    console.log(`[MockAPI] getPhotos:`, params);
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve([
          { id: 'p1', thumbnail_url: '', persona_name: '阿珍', created_at: '2026-09-01T10:00:00Z' },
          { id: 'p2', thumbnail_url: '', persona_name: '父亲', created_at: '2026-09-02T14:00:00Z' },
          { id: 'p3', thumbnail_url: '', persona_name: '工友老王', created_at: '2026-09-03T09:00:00Z' }
        ]);
      }, 400);
    });
  },

  // ================================================================
  // 人物库
  // ================================================================

  /**
   * 创建人物库条目
   * @param {Object} data - { patient_id, name, relation, photo? }
   * @returns {Promise<Object>}
   */
  createPersona: (data) => {
    console.log(`[MockAPI] createPersona:`, data);
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          id: 'aa0e8400-e29b-41d4-a716-446655440005',
          patient_id: data.patient_id,
          name: data.name,
          relation: data.relation,
          created_at: new Date().toISOString()
        });
      }, 500);
    });
  },

  /**
   * 上传语音样本并触发克隆
   * @param {string} personaId
   * @param {Blob} audio
   * @returns {Promise<Object>}
   */
  uploadVoiceSample: (personaId, audio) => {
    console.log(`[MockAPI] uploadVoiceSample: personaId=${personaId}`);
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          id: personaId,
          voice_sample_url: 'https://minio.example.com/voice/sample_001.wav',
          voice_cloned: true,
          status: 'completed'
        });
      }, 2000);
    });
  },

  /**
   * 查询人物库
   * @param {string} patientId
   * @returns {Promise<Array>}
   */
  getPersonas: (patientId) => {
    console.log(`[MockAPI] getPersonas: patientId=${patientId}`);
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve([
          { id: 'pa1', name: '阿珍', relation: '老伴', voice_cloned: false },
          { id: 'pa2', name: '父亲', relation: '父亲', voice_cloned: false },
          { id: 'pa3', name: '工友老王', relation: '工友', voice_cloned: false }
        ]);
      }, 300);
    });
  },

  // ================================================================
  // 每日简报
  // ================================================================

  /**
   * 获取指定日期简报
   * @param {string} date - 'YYYY-MM-DD'
   * @returns {Promise<Object>}
   */
  getBrief: (date) => {
    console.log(`[MockAPI] getBrief: date=${date}`);
    return new Promise((resolve) => {
      setTimeout(() => {
        // 根据日期生成略有不同的模拟数据
        const dayOffset = date ? getDayOffset(date) : 0;
        const vitalityBase = 78 - dayOffset * 3 + Math.floor(Math.random() * 10);
        const vitality = Math.max(20, Math.min(100, vitalityBase));
        resolve({
          id: 'bb0e8400-e29b-41d4-a716-446655440006',
          patient_id: '550e8400-e29b-41d4-a716-446655440001',
          date: date || '2026-09-05',
          vitality_index: vitality,
          vitality_trend_pct: dayOffset === 0 ? 5 : (Math.random() > 0.5 ? 1 : -1) * Math.floor(Math.random() * 10 + 1),
          baseline_status: 'ready',
          baseline_days_remaining: 0,
          top_topics: [
            { topic_name: '广州造船厂', gaze_duration: 45 + Math.floor(Math.random() * 20), dialogue_turns: 6 + Math.floor(Math.random() * 3) },
            { topic_name: '小时候过年', gaze_duration: 38 + Math.floor(Math.random() * 15), dialogue_turns: 4 + Math.floor(Math.random() * 3) },
            { topic_name: '粤剧《帝女花》', gaze_duration: 30 + Math.floor(Math.random() * 10), dialogue_turns: 3 + Math.floor(Math.random() * 2) }
          ],
          advice_text: '今天老人对造船厂话题表现出了很高的兴趣，可以多聊聊他在广州造船厂的工作经历。可以从"当年造的第一艘船"切入。注意避免提及已故工友，老人可能会伤感。',
          created_at: '2026-09-05T23:00:00Z'
        });
      }, 600);
    });
  },

  /**
   * 获取最新简报
   * @returns {Promise<Object>}
   */
  getLatestBrief: () => {
    console.log(`[MockAPI] getLatestBrief`);
    return MockAPI.getBrief(new Date().toISOString().split('T')[0]);
  },

  // ================================================================
  // 设备状态
  // ================================================================

  /**
   * 获取患者端在线状态
   * @returns {Promise<Object>} { online, current_state, last_heartbeat }
   */
  getDeviceStatus: () => {
    console.log(`[MockAPI] getDeviceStatus`);
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          online: true,
          current_state: 'STANDBY',
          last_heartbeat: new Date().toISOString(),
          battery_level: 85,
          wifi_signal: 'good'
        });
      }, 200);
    });
  },

  // ================================================================
  // 推送订阅
  // ================================================================

  /**
   * 注册推送订阅
   * @param {Object} subscription - PushSubscription JSON
   * @returns {Promise<Object>}
   */
  subscribePush: (subscription) => {
    console.log(`[MockAPI] subscribePush:`, subscription);
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({ success: true, id: 'push_sub_001' });
      }, 300);
    });
  }
};

// ================================================================
// 模拟辅助函数
// ================================================================

/**
 * 模拟实体抽取：根据输入文本生成模拟的实体结构
 * @param {string} text
 * @returns {Object}
 */
function mockEntityExtraction(text) {
  // 从文本中猜测年代
  let era = '1980s';
  let location = [];
  let event = '';
  let preference = [];
  let confidence = 0.82;

  if (text.includes('广州') || text.includes('广东')) {
    location.push('广州');
  }
  if (text.includes('北京')) {
    location.push('北京');
  }
  if (text.includes('上海')) {
    location.push('上海');
  }
  if (location.length === 0) {
    location.push('广州');
  }

  if (text.includes('工作') || text.includes('上班') || text.includes('厂')) {
    event = '在' + location[0] + '工作';
  } else if (text.includes('去') || text.includes('玩')) {
    event = '去' + location[0] + '玩';
  } else if (text.includes('过年') || text.includes('春节')) {
    event = '小时候过年';
  } else if (text.includes('粤剧') || text.includes('唱戏')) {
    event = '听粤剧';
    preference.push('听粤剧');
  } else {
    event = '在' + location[0] + '的生活';
  }

  if (text.includes('吃') || text.includes('饭')) {
    preference.push(location.includes('广州') ? '粤菜' : '家常菜');
  }
  if (text.includes('唱') || text.includes('粤剧')) {
    if (!preference.includes('听粤剧')) preference.push('听粤剧');
  }
  if (text.includes('棋') || text.includes('象棋')) {
    preference.push('下象棋');
  }
  if (text.includes('钓鱼')) {
    preference.push('钓鱼');
  }
  if (preference.length === 0 && Math.random() > 0.5) {
    preference.push('听粤剧');
  }

  // 提取年代
  if (text.includes('1960') || text.includes('60年代') || text.includes('六十年')) {
    era = '1960s';
  } else if (text.includes('1970') || text.includes('70年代') || text.includes('七十年')) {
    era = '1970s';
  } else if (text.includes('1980') || text.includes('80年代') || text.includes('八十年')) {
    era = '1980s';
  } else if (text.includes('1990') || text.includes('90年代') || text.includes('九十年')) {
    era = '1990s';
  }

  return {
    era: era,
    location: location,
    event: event,
    preference: preference,
    confidence: confidence,
    missing: location.length === 0 ? ['地点'] : []
  };
}

/**
 * 获取日期距今天数偏移
 */
function getDayOffset(dateStr) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(dateStr + 'T00:00:00');
  return Math.floor((today - target) / (1000 * 60 * 60 * 24));
}

/**
 * 模拟记忆列表数据
 */
function mockMemoriesData() {
  return [
    {
      id: 'm1',
      raw_text: '我爸以前在广州造船厂工作，每天下班都带我去江边看船',
      photo_url: null,
      entities: {
        era: '1980s',
        location: ['广州'],
        event: '在广州造船厂工作',
        preference: ['看船', '江边散步'],
        confidence: 0.88,
        missing: []
      },
      created_at: '2026-09-04T10:30:00Z',
      caregiver_name: '李娟'
    },
    {
      id: 'm2',
      raw_text: '小时候过年最喜欢去北京玩，天安门广场特别大',
      photo_url: null,
      entities: {
        era: '1970s',
        location: ['北京'],
        event: '去北京玩',
        preference: ['旅游'],
        confidence: 0.75,
        missing: ['人物']
      },
      created_at: '2026-09-04T14:20:00Z',
      caregiver_name: '李娟'
    },
    {
      id: 'm3',
      raw_text: '妈妈以前经常带我去听粤剧，最喜欢《帝女花》',
      photo_url: null,
      entities: {
        era: '1980s',
        location: ['广州'],
        event: '听粤剧《帝女花》',
        preference: ['听粤剧'],
        confidence: 0.91,
        missing: []
      },
      created_at: '2026-09-03T09:15:00Z',
      caregiver_name: '李娟'
    },
    {
      id: 'm4',
      raw_text: '阿珍是我老伴，我们是在厂里认识的',
      photo_url: null,
      entities: {
        era: '1970s',
        location: ['广州'],
        event: '在厂里认识阿珍',
        preference: [],
        confidence: 0.85,
        missing: ['喜好']
      },
      created_at: '2026-09-02T16:45:00Z',
      caregiver_name: '李娟'
    },
    {
      id: 'm5',
      raw_text: '退休后喜欢去公园下象棋，一坐就是一下午',
      photo_url: null,
      entities: {
        era: '2000s',
        location: ['广州'],
        event: '去公园下象棋',
        preference: ['下象棋'],
        confidence: 0.79,
        missing: []
      },
      created_at: '2026-09-01T11:00:00Z',
      caregiver_name: '李娟'
    }
  ];
}
