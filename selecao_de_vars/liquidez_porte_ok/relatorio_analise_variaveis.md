# Relatório de análise descritiva e seleção de variáveis

**Arquivo analisado:** `bases/base_final.xlsx`  
**Aba:** `base`  
**Data de geração:** 2026-05-28 09:45:19  
**Variável-alvo:** `ROA`

## 1. Visão geral da base

- Número de linhas: **615**
- Número de colunas: **85**
- Variáveis numéricas: **84**
- Variáveis categóricas/textuais: **1**
- Alvos derivados criados automaticamente: **ROA_calc**

## 2. Estatísticas descritivas numéricas — primeiras variáveis por menor missing

```text
                           variavel   n  missing  missing_pct        media          moda      mediana  desvio_padrao  coef_variacao           min           q1           q3          max  assimetria   curtose  zeros  zeros_pct_validos  valores_unicos
                         AnoMes_ord 615        0          0.0 2.019070e+05  2.014030e+05 2.019060e+05   3.165260e+02       0.001568  2.014030e+05 2.016105e+05 2.022030e+05 2.024120e+05    0.003249 -1.218834      0           0.000000              44
                                NIM 615        0          0.0 2.206593e-02 -5.366826e-02 1.621316e-02   2.408319e-02       1.091420 -5.366826e-02 7.640098e-03 3.173084e-02 1.183684e-01    1.149444  2.356474      0           0.000000             615
                                ROA 615        0          0.0 4.586147e-03 -2.819909e-02 4.070482e-03   4.250306e-03       0.926770 -2.819909e-02 2.402274e-03 6.722380e-03 2.079891e-02   -1.117102 12.325184      0           0.000000             615
                           ROA_calc 615        0          0.0 4.586147e-03 -2.819909e-02 4.070482e-03   4.250306e-03       0.926770 -2.819909e-02 2.402274e-03 6.722380e-03 2.079891e-02   -1.117102 12.325184      0           0.000000             615
                                ROE 615        0          0.0 5.118409e-02 -2.896455e-01 4.844956e-02   4.415355e-02       0.862642 -2.896455e-01 3.172364e-02 7.542089e-02 1.916161e-01   -1.926695 14.433008      0           0.000000             615
                        ativo_total 615        0          0.0 3.243602e+11  3.865583e+09 5.206756e+10   5.372277e+11       1.656269  3.865583e+09 1.570983e+10 2.651195e+11 2.442450e+12    1.868224  2.511162      0           0.000000             615
                    ativo_total_log 615        0          0.0 2.502614e+01  2.207539e+01 2.467582e+01   1.783630e+00       0.071271  2.207539e+01 2.347757e+01 2.630263e+01 2.852404e+01    0.440569 -1.035931      0           0.000000             615
             ativos_sobre_captacoes 615        0          0.0 1.603055e+00  1.082702e+00 1.340763e+00   6.600052e-01       0.411717  1.082702e+00 1.266080e+00 1.492748e+00 3.791152e+00    2.036046  2.770902      0           0.000000             615
             ativos_sobre_depositos 615        0          0.0 3.405553e+00  1.230473e+00 2.837037e+00   2.464547e+00       0.723685  1.230473e+00 1.642766e+00 4.211757e+00 1.589264e+01    2.586821  8.425319      0           0.000000             615
                          captacoes 615        0          0.0 2.375460e+11  2.927210e+09 3.039425e+10   4.104764e+11       1.727987  2.927210e+09 1.038345e+10 1.913352e+11 1.941502e+12    2.025329  3.303205      0           0.000000             615
                      captacoes_log 615        0          0.0 2.461391e+01  2.179733e+01 2.413754e+01   1.837690e+00       0.074661  2.179733e+01 2.306349e+01 2.597731e+01 2.829450e+01    0.489864 -1.038963      0           0.000000             615
        captacoes_sobre_ativo_total 615        0          0.0 6.904265e-01  2.637721e-01 7.458438e-01   1.678854e-01       0.243162  2.637721e-01 6.699061e-01 7.898396e-01 9.236154e-01   -1.346951  0.791762      0           0.000000             615
               controle_estrangeiro 615        0          0.0 1.430894e-01  0.000000e+00 0.000000e+00   3.504491e-01       2.449161  0.000000e+00 0.000000e+00 0.000000e+00 1.000000e+00    2.043521  2.183068    527           0.856911               2
                        crise_covid 615        0          0.0 2.959350e-01  0.000000e+00 0.000000e+00   4.568335e-01       1.543695  0.000000e+00 0.000000e+00 1.000000e+00 1.000000e+00    0.896304 -1.200554    433           0.704065               2
                          crise_nme 615        0          0.0 2.504065e-01  0.000000e+00 0.000000e+00   4.335998e-01       1.731584  0.000000e+00 0.000000e+00 5.000000e-01 1.000000e+00    1.155018 -0.668116    461           0.749593               2
                          depositos 615        0          0.0 1.087560e+11  1.554227e+09 1.393966e+10   1.908198e+11       1.754568  1.554227e+09 7.866189e+09 8.445573e+10 8.990063e+11    2.088014  3.454461      0           0.000000             615
                  depositos_a_prazo 615        0          0.0 6.652907e+10  1.012819e+09 9.246094e+09   1.130978e+11       1.699976  1.012819e+09 5.720515e+09 6.899500e+10 5.351900e+11    2.136183  3.755021      0           0.000000             615
              depositos_a_prazo_log 615        0          0.0 2.354585e+01  2.073602e+01 2.294748e+01   1.693313e+00       0.071916  2.073602e+01 2.246734e+01 2.495731e+01 2.700591e+01    0.436929 -0.912548      0           0.000000             615
depositos_a_prazo_sobre_ativo_total 615        0          0.0 2.819874e-01  2.661318e-02 2.537507e-01   1.706145e-01       0.605043  2.661318e-02 1.386118e-01 4.307976e-01 6.891897e-01    0.560824 -0.742153      0           0.000000             615
                  depositos_a_vista 615        0          0.0 1.214153e+10  1.146529e+07 1.161526e+09   2.418860e+10       1.992220  1.146529e+07 4.899878e+08 5.012060e+09 1.183475e+11    2.449837  5.642224      0           0.000000             615
```

## 3. Estatísticas descritivas categóricas

```text
   variavel   n  missing  missing_pct  valores_unicos  moda  freq_moda  freq_moda_pct
id_entidade 615        0          0.0              14 ABCB4         44       0.071545
```

## 4. Diagnóstico de qualidade da base

### 4.1 Variáveis com maior percentual de missing

```text
                            variavel  missing  missing_pct   dtype  valores_unicos
                          AnoMes_ord        0          0.0   int64              44
                         id_entidade        0          0.0  object              14
                           trimestre        0          0.0   int64               4
                         ativo_total        0          0.0 float64             615
                    disponibilidades        0          0.0 float64             615
                 permanente_ajustado        0          0.0 float64             615
                  patrimonio_liquido        0          0.0 float64             615
                       passivo_total        0          0.0 float64             615
                       lucro_liquido        0          0.0 float64             615
                           captacoes        0          0.0 float64             615
                           depositos        0          0.0 float64             615
                   depositos_a_prazo        0          0.0 float64             615
                   depositos_a_vista        0          0.0 float64             615
            despesas_administrativas        0          0.0 float64             615
                despesas_tributarias        0          0.0 float64             615
                despesas_de_captacao        0          0.0 float64             615
despesas_de_intermediacao_financeira        0          0.0 float64             615
                 despesas_de_pessoal        0          0.0 float64             615
                operacoes_de_credito        0          0.0 float64             615
 provisao_sobre_operacoes_de_credito        0          0.0 float64             615
```

### 4.2 Variáveis com baixa informação

Sem registros.

### 4.3 Possíveis problemas para transformações logarítmicas

Estas variáveis têm valores menores ou iguais a zero. Caso sejam usadas em log, exigem tratamento prévio.

```text
                                                 variavel  valores_menores_ou_iguais_a_zero  pct_validos           min
                                 despesas_administrativas                               615     1.000000 -1.198609e+10
                 despesas_de_intermediacao_sobre_receitas                               615     1.000000 -4.398749e+00
                                     despesas_tributarias                               615     1.000000 -4.814714e+09
                                     despesas_de_captacao                               615     1.000000 -1.048998e+11
                     despesas_de_intermediacao_financeira                               615     1.000000 -1.471732e+11
                                      despesas_de_pessoal                               615     1.000000 -1.356659e+10
                      despesas_de_captacao_sobre_receitas                               615     1.000000 -1.676952e+00
                      despesas_tributarias_sobre_receitas                               615     1.000000 -1.581038e-01
                              despesas_adm_sobre_receitas                               615     1.000000 -6.411132e-01
                       despesas_de_pessoal_sobre_receitas                               615     1.000000 -7.313307e-01
                                   flag_outlier__nsfr_dec                               601     0.977236  0.000000e+00
                                    flag_outlier__lcr_dec                               601     0.977236  0.000000e+00
                   provisoes_de_credito_sobre_ativo_total                               583     0.947967 -7.277037e-02
                      provisao_sobre_operacoes_de_credito                               583     0.947967 -6.034187e+10
resultado_de_provisao_para_creditos_de_dificil_liquidacao                               580     0.943089 -2.200910e+10
            resultado_de_provisao_pcddl_sobre_ativo_total                               580     0.943089 -3.612717e-02
                                     controle_estrangeiro                               527     0.856911  0.000000e+00
                                                crise_nme                               461     0.749593  0.000000e+00
                                              crise_covid                               433     0.704065  0.000000e+00
                                           gap_de_funding                               326     0.530081 -4.684772e-01
```

## 5. Seleção de variáveis para regressão linear

Parâmetros usados:

- Máximo de missing permitido nos preditores: **40.00%**
- Limiar de correlação entre preditores para poda: **0.95**
- Limiar de VIF: **10.00**
- Top-k do teste F univariado: **25**
- Correlação mínima absoluta com o alvo: **0.0000**
- Variáveis temporais incluídas: **False**
- Dummies de entidade incluídas: **False**

### 5.1 Variáveis mais correlacionadas com o alvo

```text
                              variavel  corr_com_alvo  abs_corr_com_alvo  n_corr
           captacoes_sobre_ativo_total      -0.255581           0.255581     615
  operacoes_de_credito_sobre_captacoes       0.249096           0.249096     615
                ativos_sobre_captacoes       0.242112           0.242112     615
                        gap_de_funding       0.226836           0.226836     615
   depositos_a_prazo_sobre_ativo_total      -0.225672           0.225672     615
                patrimonio_liquido_log       0.213320           0.213320     615
                 depositos_a_vista_log       0.179095           0.179095     615
  operacoes_de_credito_sobre_depositos       0.169820           0.169820     615
                       ativo_total_log       0.163945           0.163945     615
operacoes_de_credito_sobre_ativo_total       0.151987           0.151987     615
                ativos_sobre_depositos       0.149800           0.149800     615
                         captacoes_log       0.115845           0.115845     615
               permanente_ajustado_log       0.115203           0.115203     615
                         depositos_log       0.112375           0.112375     615
                  disponibilidades_log       0.078425           0.078425     615
                 depositos_a_prazo_log       0.070171           0.070171     615
      disponibilidades_sobre_depositos       0.059212           0.059212     615
                             crise_nme      -0.056702           0.056702     615
                               estatal       0.052225           0.052225     615
   depositos_a_vista_sobre_ativo_total       0.051305           0.051305     615
                           crise_covid       0.030484           0.030484     615
                  controle_estrangeiro       0.028842           0.028842     615
                indice_de_imobilizacao      -0.010803           0.010803     615
                     liquidez_imediata       0.002606           0.002606     615
```

### 5.2 Ranking por LassoCV e teste F

```text
                              variavel   f_score  p_value_f_regression  lasso_coef_padronizado  abs_lasso_coef  lasso_alpha  rank_f_score  rank_lasso  selecionada_f_test_top_k  selecionada_lasso  selecionada_union
                patrimonio_liquido_log 29.224629          9.243998e-08                0.007413        0.007413     0.000004           5.0         1.0                      True               True               True
               permanente_ajustado_log  8.245025          4.227550e-03               -0.005204        0.005204     0.000004          10.0         2.0                      True               True               True
                        gap_de_funding 33.252589          1.283772e-08               -0.003960        0.003960     0.000004           3.0         3.0                      True               True               True
                  disponibilidades_log  3.793580          5.190562e-02               -0.003363        0.003363     0.000004          11.0         4.0                      True               True               True
operacoes_de_credito_sobre_ativo_total 14.495116          1.546496e-04                0.003337        0.003337     0.000004           8.0         5.0                      True               True               True
                 depositos_a_vista_log 20.313619          7.874711e-06                0.001506        0.001506     0.000004           6.0         6.0                      True               True               True
                indice_de_imobilizacao  0.071547          7.891869e-01                0.001302        0.001302     0.000004          18.0         7.0                      True               True               True
                     liquidez_imediata  0.004162          9.485833e-01                0.001292        0.001292     0.000004          19.0         8.0                      True               True               True
                ativos_sobre_depositos 14.071438          1.926917e-04                0.001179        0.001179     0.000004           9.0         9.0                      True               True               True
   depositos_a_prazo_sobre_ativo_total 32.893852          1.529358e-08               -0.001023        0.001023     0.000004           4.0        10.0                      True               True               True
  operacoes_de_credito_sobre_captacoes 40.552253          3.756602e-10                0.000653        0.000653     0.000004           2.0        11.0                      True               True               True
   depositos_a_vista_sobre_ativo_total  1.617795          2.038818e-01               -0.000379        0.000379     0.000004          15.0        12.0                      True               True               True
                  controle_estrangeiro  0.510358          4.752561e-01               -0.000277        0.000277     0.000004          17.0        13.0                      True               True               True
  operacoes_de_credito_sobre_depositos 18.203140          2.299626e-05               -0.000233        0.000233     0.000004           7.0        14.0                      True               True               True
           captacoes_sobre_ativo_total 42.840423          1.255802e-10               -0.000106        0.000106     0.000004           1.0        15.0                      True               True               True
                             crise_nme  1.977235          1.601887e-01               -0.000083        0.000083     0.000004          13.0        16.0                      True               True               True
                               estatal  1.676516          1.958755e-01               -0.000014        0.000014     0.000004          14.0        17.0                      True               True               True
      disponibilidades_sobre_depositos  2.156796          1.424533e-01               -0.000000        0.000000     0.000004          12.0        18.0                      True              False               True
                           crise_covid  0.570179          4.504778e-01                0.000000        0.000000     0.000004          16.0        18.0                      True              False               True
```

### 5.3 Variáveis removidas por multicolinearidade entre preditores

```text
     variavel_removida            variavel_mantida  corr_entre_variaveis  abs_corr_alvo_removida  abs_corr_alvo_mantida                             motivo
       ativo_total_log      patrimonio_liquido_log              0.987401                0.163945               0.213320 correlacao_preditiva_acima_de_0.95
 depositos_a_prazo_log               depositos_log              0.977626                0.070171               0.112375 correlacao_preditiva_acima_de_0.95
ativos_sobre_captacoes captacoes_sobre_ativo_total              0.965349                0.242112               0.255581 correlacao_preditiva_acima_de_0.95
         depositos_log               captacoes_log              0.959197                0.112375               0.115845 correlacao_preditiva_acima_de_0.95
         captacoes_log      patrimonio_liquido_log              0.958419                0.115845               0.213320 correlacao_preditiva_acima_de_0.95
```

### 5.4 Variáveis removidas por VIF

```text
                     variavel_removida  vif_no_momento_remocao  abs_corr_com_alvo    motivo
                indice_de_imobilizacao               12.621254           0.010803 VIF>10.00
   depositos_a_vista_sobre_ativo_total               10.416199           0.051305 VIF>10.00
                  disponibilidades_log               27.611849           0.078425 VIF>10.00
               permanente_ajustado_log               21.406060           0.115203 VIF>10.00
operacoes_de_credito_sobre_ativo_total               51.999335           0.151987 VIF>10.00
                 depositos_a_vista_log               10.686095           0.179095 VIF>10.00
                        gap_de_funding               13.836077           0.226836 VIF>10.00
```

### 5.5 Variáveis finais sugeridas

```text
                            variavel  corr_com_alvo  abs_corr_com_alvo      vif   f_score  p_value_f_regression  lasso_coef_padronizado  abs_lasso_coef
              patrimonio_liquido_log       0.213320           0.213320 1.730073 29.224629          9.243998e-08                0.007413        0.007413
                   liquidez_imediata       0.002606           0.002606 4.398925  0.004162          9.485833e-01                0.001292        0.001292
              ativos_sobre_depositos       0.149800           0.149800 5.008169 14.071438          1.926917e-04                0.001179        0.001179
 depositos_a_prazo_sobre_ativo_total      -0.225672           0.225672 4.744295 32.893852          1.529358e-08               -0.001023        0.001023
operacoes_de_credito_sobre_captacoes       0.249096           0.249096 6.751880 40.552253          3.756602e-10                0.000653        0.000653
                controle_estrangeiro       0.028842           0.028842 1.363514  0.510358          4.752561e-01               -0.000277        0.000277
operacoes_de_credito_sobre_depositos       0.169820           0.169820 9.047959 18.203140          2.299626e-05               -0.000233        0.000233
         captacoes_sobre_ativo_total      -0.255581           0.255581 2.494821 42.840423          1.255802e-10               -0.000106        0.000106
                           crise_nme      -0.056702           0.056702 1.318509  1.977235          1.601887e-01               -0.000083        0.000083
                             estatal       0.052225           0.052225 2.022636  1.676516          1.958755e-01               -0.000014        0.000014
    disponibilidades_sobre_depositos       0.059212           0.059212 4.032558  2.156796          1.424533e-01               -0.000000        0.000000
                         crise_covid       0.030484           0.030484 1.195823  0.570179          4.504778e-01                0.000000        0.000000
```

## 6. Fórmula sugerida para posterior regressão linear em `statsmodels`

```python
formula = "Q('ROA') ~ Q('patrimonio_liquido_log') + Q('liquidez_imediata') + Q('ativos_sobre_depositos') + Q('depositos_a_prazo_sobre_ativo_total') + Q('operacoes_de_credito_sobre_captacoes') + Q('controle_estrangeiro') + Q('operacoes_de_credito_sobre_depositos') + Q('captacoes_sobre_ativo_total') + Q('crise_nme') + Q('estatal') + Q('disponibilidades_sobre_depositos') + Q('crise_covid')"
```

## 7. Interpretação metodológica

A seleção foi construída como etapa exploratória para reduzir dimensionalidade e problemas de multicolinearidade antes da regressão linear. O procedimento combina: filtros de qualidade dos dados, associação linear univariada com a variável-alvo, regularização L1 via LassoCV, poda de pares altamente correlacionados e poda iterativa por VIF. Em aplicações acadêmicas, recomenda-se que a especificação final seja validada por fundamentação teórica, coerência econômica, diagnóstico de resíduos e testes de robustez.

## 8. Referências metodológicas em formato ABNT

GUYON, Isabelle; ELISSEEFF, André. An introduction to variable and feature selection. *Journal of Machine Learning Research*, v. 3, p. 1157-1182, 2003.

TIBSHIRANI, Robert. Regression shrinkage and selection via the lasso. *Journal of the Royal Statistical Society: Series B*, v. 58, n. 1, p. 267-288, 1996.

O'BRIEN, Robert M. A caution regarding rules of thumb for variance inflation factors. *Quality & Quantity*, v. 41, p. 673-690, 2007.

JAMES, Gareth et al. *An introduction to statistical learning: with applications in R*. 2. ed. New York: Springer, 2021.
