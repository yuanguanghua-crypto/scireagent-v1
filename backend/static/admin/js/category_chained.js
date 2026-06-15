/**
 * Category L1 → L2 联动 + L3 自由文本
 * 
 * 在 Django Admin 的产品编辑页面中：
 * - 选择 L1 后，L2 下拉菜单自动更新
 * - L3 是文本输入框（可选）
 * - 保存时 L2|L3 拼接存入 category_l2 字段
 */

(function() {
    'use strict';

    // L2 选项映射（L1 code → L2 options）
    const L2_OPTIONS = {
        'nucleotides_nucleosides': [
            ['fluorescent_labeled', '荧光标记 (Fluorescent Labeled)'],
            ['biotin_labeled', '生物素标记 (Biotin Labeled)'],
            ['click_chemistry_ntp', '点击化学 (Click Chemistry)'],
            ['modified_utp', '修饰 UTP (Modified UTP)'],
            ['modified_dutp', '修饰 dUTP (Modified dUTP)'],
            ['modified_ctp_dctp', '修饰 CTP/dCTP (Modified CTP/dCTP)'],
            ['modified_atp_datp', '修饰 ATP/dATP (Modified ATP/dATP)'],
            ['modified_gtp_dgtp', '修饰 GTP/dGTP (Modified GTP/dGTP)'],
            ['deaza', '7-脱氮核苷酸 (7-Deaza Nucleotides)'],
            ['thio_nucleotides', '硫代核苷酸 (Thio Nucleotides)'],
            ['other_nucleotides', '其他核苷酸 (Other Nucleotides)'],
        ],
        'click_chemistry': [
            ['alkyne_reagents', '炔基试剂 (Alkyne Reagents)'],
            ['azide_reagents', '叠氮试剂 (Azide Reagents)'],
            ['dbco_reagents', 'DBCO 试剂 (DBCO Reagents)'],
            ['tco_reagents', 'TCO 试剂 (TCO Reagents)'],
            ['tetrazine_reagents', '四嗪试剂 (Tetrazine Reagents)'],
            ['auxiliary_reagents', '辅助 Cu(I) 试剂 (Auxiliary Cu(I) Reagents)'],
            ['other_click', '其他点击化学试剂 (Other Click Reagents)'],
        ],
        'molecular_biology': [
            ['pcr', 'PCR 及试剂 (PCR & Reagents)'],
            ['real_time_pcr', '实时荧光 PCR (Real-Time PCR)'],
            ['rt_pcr', '逆转录 (Reverse Transcription)'],
            ['isothermal_amplification', '等温扩增 (Isothermal Amplification)'],
            ['rna_dna_prep', '核酸提取纯化 (RNA/DNA Preparation)'],
            ['enzymes_markers', '酶与蛋白 Marker (Enzymes & Markers)'],
            ['cloning', '克隆与突变 (Cloning & Mutagenesis)'],
            ['other_mol_bio', '其他分子生物学 (Other Molecular Biology)'],
        ],
        'proteins': [
            ['enzymes', '酶 (Enzymes)'],
            ['kinases', '激酶 (Kinases)'],
            ['phosphatases', '磷酸酶 (Phosphatases)'],
            ['gtpases', '小 GTP 酶 (Small GTPases)'],
            ['signal_transduction', '信号转导蛋白 (Signal Transduction)'],
            ['other_proteins', '其他蛋白 (Other Proteins)'],
        ],
        'probes_epigenetics': [
            ['fluorescent_dyes', '反应性荧光染料 (Reactive Fluorescent Dyes)'],
            ['dna_labeling', 'DNA 标记 (DNA Labeling)'],
            ['rna_labeling', 'RNA 标记 (RNA Labeling)'],
            ['protein_labeling', '蛋白标记 (Protein Labeling)'],
            ['cell_labeling', '细胞标记 (Cell Labeling)'],
            ['epigenetics', '表观遗传学 (Epigenetics)'],
            ['other_probes', '其他探针 (Other Probes)'],
        ],
        'rna_technologies': [
            ['rna_synthesis', 'RNA 合成 (RNA Synthesis)'],
            ['rna_labeling_modification', 'RNA 标记与修饰 (RNA Labeling & Modification)'],
            ['rna_analysis_detection', 'RNA 分析与检测 (RNA Analysis & Detection)'],
            ['other_rna', '其他 RNA 技术 (Other RNA Technologies)'],
        ],
        'antibodies_antigens': [
            ['antibodies', '抗体 (Antibodies)'],
            ['microbial_antigens', '微生物抗原 (Microbial Antigens)'],
            ['viral_antigens', '病毒抗原 (Viral Antigens)'],
            ['other_antibodies', '其他抗体/抗原 (Other Antibodies/Antigens)'],
        ],
        'crystallography_cryoem': [
            ['screening_kits', '筛选试剂盒 (Screening Kits)'],
            ['optimization_phasing', '优化与相位 (Optimization & Phasing)'],
            ['membrane_proteins', '膜蛋白 (Membrane Proteins)'],
            ['cryoem_grids', '冷冻电镜载网 (Cryo-EM Grids)'],
            ['plates_sealings', '板材与密封 (Plates & Sealings)'],
            ['other_crystallography', '其他晶体学 (Other Crystallography)'],
        ],
        'custom_synthesis': [
            ['custom_nucleotides', '定制核苷酸 (Custom Nucleotides)'],
            ['custom_oligos', '定制寡核苷酸 (Custom Oligos)'],
            ['custom_probes', '定制探针 (Custom Probes)'],
            ['other_custom', '其他定制服务 (Other Custom Services)'],
        ],
    };

    function init() {
        // 找到 L1 和 L2 的 select 元素
        const l1Select = document.getElementById('id_category_l1');
        const l2Input = document.getElementById('id_category_l2');
        
        if (!l1Select || !l2Input) return;

        // 获取当前值
        const currentL1 = l1Select.value;
        const currentL2Value = l2Input.value;
        
        // 解析 category_l2: 可能是 "l2_code" 或 "l2_code | l3_text"
        let currentL2 = '';
        let currentL3 = '';
        if (currentL2Value) {
            const parts = currentL2Value.split('|').map(s => s.trim());
            currentL2 = parts[0] || '';
            currentL3 = parts[1] || '';
        }

        // 创建 L2 下拉 select 元素
        const l2Select = document.createElement('select');
        l2Select.id = 'id_category_l2_select';
        l2Select.name = 'category_l2_select';
        l2Select.className = l2Input.className || 'vSelect';
        
        // 创建 L3 文本输入框
        const l3Input = document.createElement('input');
        l3Input.type = 'text';
        l3Input.id = 'id_category_l3';
        l3Input.name = 'category_l3';
        l3Input.placeholder = '具体修饰类型（可选），例如：Cy3-UTP, N1-Methylpseudouridine';
        l3Input.className = l2Input.className || 'vTextField';
        l3Input.value = currentL3;

        // 隐藏原始 category_l2 输入框
        l2Input.style.display = 'none';
        
        // 在 L2 位置插入新的 select 和 L3 输入框
        const l2Parent = l2Input.parentNode;
        l2Parent.appendChild(l2Select);
        
        // 创建 L3 容器
        const l3Container = document.createElement('div');
        l3Container.style.marginTop = '8px';
        l3Container.innerHTML = '<label style="display:block;margin-bottom:4px;font-weight:600;">三级分类 (L3) — 具体修饰类型（可选）</label>';
        l3Container.appendChild(l3Input);
        l2Parent.appendChild(l3Container);

        // 更新 L2 下拉选项
        function updateL2Options() {
            const l1Value = l1Select.value;
            const options = L2_OPTIONS[l1Value] || [];
            
            l2Select.innerHTML = '<option value="">-- 请选择二级分类 --</option>';
            options.forEach(function(opt) {
                const option = document.createElement('option');
                option.value = opt[0];
                option.textContent = opt[1];
                if (opt[0] === currentL2) {
                    option.selected = true;
                }
                l2Select.appendChild(option);
            });
        }

        // 同步 L2+L3 到隐藏的 category_l2 字段
        function syncCategoryL2() {
            const l2 = l2Select.value;
            const l3 = l3Input.value.trim();
            if (l2 && l3) {
                l2Input.value = l2 + ' | ' + l3;
            } else if (l2) {
                l2Input.value = l2;
            } else {
                l2Input.value = '';
            }
        }

        // 事件监听
        l1Select.addEventListener('change', function() {
            updateL2Options();
            syncCategoryL2();
        });
        
        l2Select.addEventListener('change', syncCategoryL2);
        l3Input.addEventListener('input', syncCategoryL2);

        // 初始化
        updateL2Options();
    }

    // DOM 加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
