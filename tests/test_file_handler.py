import filecmp
import sys

from pathlib import Path

import numpy as np
import pytest
import pandas as pd
import json
import shutil
sys.path.insert(0, 'cognival')

from handlers.file_handler import *

@pytest.fixture
def config(tmpdir):
    config_dict = {
        "PATH": "",
        "cogDataConfig": {
            "zuco-eeg": {
                "dataset": "cognitive-data/eeg/zuco/zuco_scaled.txt",
                "modality": "eeg",
                "features": [
                    "ALL_DIM"
                ],
                "type": "multivariate_output",
                "wordEmbSpecifics": {
                    "glove-50": {
                        "activations": [
                            "relu"
                        ],
                        "batch_size": [
                            128
                        ],
                        "cv_split": 3,
                        "epochs": [
                            100
                        ],
                        "layers": [
                            [
                                26
                            ],
                            [
                                30
                            ],
                            [
                                20
                            ],
                            [
                                5
                            ]
                        ],
                        "validation_split": 0.2
                    }
                }
            }
        },
        "n_proc": 40,
        "folds": 5,
        "outputDir": str(tmpdir),
        "seed": 123,
        "run_id": 1,
        "wordEmbConfig": {
            "glove-50": {
                "chunk_number": 4,
                "chunked": 1,
                "chunked_file": "glove-50",
                "ending": ".txt",
                "path": "reference/chunked_embeddings/glove.6B.50d.txt",
                "random_embedding": None,
            }
        }
    }
    
    tmpdir.mkdir('output')
    with open(tmpdir / 'output' / 'config.json', 'w') as f:
        json.dump(config_dict, f)
    return config_dict

@pytest.fixture
def results():
    logging = {'folds': [{'ACTIVATION': 'relu', 'BATCH_SIZE': 128, 'EPOCHS': 100, 'INPUT_DIM': 50, 'LAYERS': [5], 'OUTPUT_DIM': 105, 'MSE_PREDICTION_ALL_DIM:': [0.008450321076835802, 0.005430305245934602, 0.005089805156944887, 0.006516788380558457, 0.011858743193404834, 0.005530381214320247, 0.008523528788031729, 0.007859309151975791, 0.009937974664590087, 0.01267818477667079, 0.009335043481256872, 0.0048746837857379065, 0.009340689565691764, 0.007359499260523418, 0.01127502341154575, 0.013480642344498656, 0.00786389868056336, 0.01253602044694815, 0.012187992431031953, 0.007725461291570377, 0.01007202842147161, 0.009999273989230673, 0.009758725013173606, 0.005909310146023649, 0.004041934456466951, 0.01129813383374466, 0.01441005977223278, 0.00893000849770723, 0.008794927985866608, 0.006387328039390285, 0.0017534214974104629, 0.01244194765126577, 0.012943025164100775, 0.011478759064776547, 0.009396412736353964, 0.00607837228840002, 0.010022746935510933, 0.010695391670258866, 0.00960434361330253, 0.00979984501850467, 0.011152288342170708, 0.011158179639521485, 0.010108821327608382, 0.010170903326145474, 0.00814850530426166, 0.006071881727530583, 0.009401768049789882, 0.011778315154228764, 0.011301423400744538, 0.00875554487420991, 0.008942417681111352, 0.011567288554920582, 0.01101270438984888, 0.011199599140207624, 0.011194044540792644, 0.011776244375963491, 0.007163477111091334, 0.008020238121695021, 0.01216974776505914, 0.012209850479716509, 0.006236481819117854, 0.007697214202791159, 0.011606872327079491, 0.013958189060972678, 0.007782691333553772, 0.006745536622104312, 0.003802346289790525, 0.0055099615205673365, 0.008853518166306685, 0.009564597826091445, 0.015422337629465951, 0.01225927050645071, 0.006375466077841941, 0.006747477011273077, 0.00807186339132025, 0.01147179319434488, 0.013466250253921008, 0.011424745867194115, 0.006399744813968271, 0.0075029858108204735, 0.011812665685334013, 0.010507710635479393, 0.007472783057941712, 0.009788859454901848, 0.007856046355051062, 0.008104903680923942, 0.008406965158324075, 0.006983130588130061, 0.005320370617213805, 0.009704894848771267, 0.006862961470976834, 0.00686423518958466, 0.006763885218758564, 0.009004926772171977, 0.005032878303981363, 0.010722217705138317, 0.007040943512548193, 0.0071525881165115995, 0.004835693019422062, 0.004389917942756288, 0.009662952116193946, 0.006308599383432429, 0.006131571959418603, 0.006203283183445324, 1.8782576151683427e-06], 'MSE_PREDICTION:': 0.008845807061042366, 'LOSS: ': [0.260642214640779, 0.22101417760659053, 0.18741235104506734, 0.1512738781029548, 0.11489731125737974, 0.084752550466936, 0.06288760976375202, 0.048221296901341804, 0.03852890376722575, 0.03196076618221213, 0.027294536020042573, 0.0238674830264534, 0.021298176918020603, 0.019311848192096696, 0.017762089013067774, 0.016515944556608566, 0.015513166225256664, 0.01468916583109097, 0.014020252432807166, 0.013435159234154363, 0.012931507584428549, 0.012529689823170547, 0.01214337894046936, 0.011816641715856053, 0.011535647831302821, 0.011271989047569313, 0.011045779743431678, 0.010839963666058739, 0.010646593058394315, 0.010480770099962712, 0.010323310648194384, 0.010185127429333744, 0.010052392745725825, 0.009930948530138659, 0.009820177669894847, 0.009712792340454662, 0.009610211958619424, 0.00952528610164758, 0.00944045813819299, 0.009356294820216065, 0.009283740236537656, 0.00921621795026925, 0.009145076791568611, 0.009078143269862393, 0.009019169630955278, 0.008953342885506956, 0.008910787168978435, 0.008852715160220313, 0.008815761622145061, 0.0087592306475819, 0.008712597956411241, 0.00867523320092043, 0.008636477390743094, 0.00860953892167127, 0.008568170061142473, 0.008548042924892002, 0.008513287172296841, 0.008493908283037156, 0.00847168049709616, 0.008444954790258958, 0.008426293469643468, 0.008402963043972766, 0.008389891409453416, 0.00838145619375181, 0.008369331637993091, 0.008350228262545134, 0.008333550536517182, 0.008323334821747326, 0.008311798879880233, 0.00830996380359416, 0.008300718135133592, 0.008297275203045308, 0.008282288088932582, 0.008278840330311428, 0.008271718446735106, 0.008261960458811212, 0.008268121860946583, 0.008252625329835058, 0.008245148853150717, 0.0082417448656406, 0.008240602322185972, 0.00823016547552796, 0.008232766358487725, 0.008223147603638724, 0.008218352572291764, 0.008211108698757776, 0.008208761930364902, 0.008208817056716552, 0.008203946909881576, 0.008204527739302438, 0.008196460124425806, 0.008196608208565057, 0.008195863516594582, 0.008184145496614286, 0.008194317280327813, 0.008187121581825177, 0.008195520124906708, 0.00817984816846107, 0.008173449317743034, 0.008179055656348794], 'VALIDATION_LOSS: ': [0.2366156741395011, 0.2036706325528142, 0.1697889782107986, 0.13269658713369398, 0.09863074392348796, 0.07294367875780787, 0.05510438030009513, 0.04306835408235814, 0.035077525946023584, 0.029577267627503064, 0.025617047115131183, 0.0226472300832515, 0.02040885579031151, 0.018737479580102023, 0.01735422291510456, 0.01630319398198579, 0.015431205129569716, 0.014691296813858522, 0.014097035345104005, 0.01359070198716702, 0.013139542351636264, 0.012795792196180907, 0.012446990233843212, 0.012155069239638947, 0.011908925289439189, 0.011650957505557093, 0.011471617239731568, 0.01126719256387548, 0.01108801182549637, 0.01093417151017232, 0.010816460307519715, 0.010667995082678738, 0.0105451865753791, 0.010410728858778247, 0.010295376726971553, 0.010190713096286979, 0.010080994934671454, 0.010002761234616016, 0.009905689647672949, 0.0098292134959508, 0.009746268123119801, 0.009672709721120986, 0.009601932888789041, 0.00953425571333628, 0.009484346175717341, 0.00941484700049366, 0.009364417538762809, 0.009309927804266906, 0.009237514657748712, 0.00918766749916492, 0.009147932386590733, 0.009117590990644676, 0.00907264909407756, 0.009044567520196015, 0.008996541220303233, 0.008967764479843704, 0.008946917360989718, 0.008909246137550285, 0.008884450960512812, 0.008865125550029872, 0.008829529036406998, 0.008822998580139678, 0.00880108005157462, 0.00877279632755586, 0.00877061539382727, 0.008745964893416778, 0.008735265655515788, 0.008722033276147134, 0.00872335516408578, 0.0087096413972231, 0.008694922543122425, 0.00869052018970251, 0.008662863189841176, 0.008666820980765082, 0.008658204378711211, 0.008649985694715211, 0.008640972740791581, 0.008625090085864963, 0.008624791369043492, 0.008610596883113499, 0.008615717213522564, 0.008621652395249129, 0.008589327285015906, 0.008598913391073187, 0.008594917555761946, 0.008572355659493993, 0.008589283112917576, 0.008574581145680882, 0.008574465781942502, 0.008598072767570929, 0.008570298916092506, 0.008581342681817285, 0.008571679180896317, 0.008575401601714414, 0.00855078171189125, 0.008578744831609654, 0.008564617498791791, 0.008547275777425136, 0.00854044600862551, 0.008555561108318894]}], 'wordEmbedding': 'glove-50', 'cognitiveData': 'zuco-eeg', 'feature': 'ALL_DIM', 'AVERAGE_MSE_ALL_DIM': [0.008627047469720104, 0.005499145862835013, 0.005211735904384024, 0.006558321085677901, 0.01124020937797977, 0.005353965532612394, 0.008486128025197773, 0.0077905575028023285, 0.010388307489433693, 0.013189625440000685, 0.00912137818576895, 0.00517818016892487, 0.009415467229329667, 0.007530914243734736, 0.01120021218561148, 0.013674447027299651, 0.008279562741249354, 0.01246660746829157, 0.012377547547016168, 0.007171902037472119, 0.010151079856777247, 0.010190606283531583, 0.009546215678481221, 0.0054180668853419794, 0.003467299663611833, 0.01213104257179003, 0.01485492568693462, 0.008945591172499897, 0.008191513965719072, 0.006200375500944195, 0.0018367249454278908, 0.013200668373441577, 0.013289329019007224, 0.011076920778537912, 0.008846804177263357, 0.0058200309683406875, 0.01063181512670119, 0.010855088827006415, 0.009204021173201299, 0.009344554643449543, 0.01103469470866858, 0.010188434718675896, 0.009770655076229045, 0.009404891184335847, 0.007473094844105553, 0.005723114530901703, 0.009374096088006757, 0.011984843949096522, 0.011206814616655198, 0.008292679831638543, 0.008374332776354593, 0.011330492183946193, 0.01109749850633214, 0.011013615783867118, 0.011004686543604833, 0.011212355336453376, 0.00738625461977563, 0.007953471383988817, 0.011864861489012488, 0.011991030626382659, 0.0061962425350784965, 0.007643280844344175, 0.011580966023128195, 0.013838905846389731, 0.007471161178765166, 0.006755788520566472, 0.0037764133188412027, 0.005336536052003479, 0.008728096159882093, 0.00957473339449159, 0.01514496920867509, 0.011956136901097132, 0.0060293459955828785, 0.006480718992208376, 0.008153347358436988, 0.01149426232395481, 0.013235277125714992, 0.011041043536589471, 0.00601483780665254, 0.007408926636682053, 0.011436505765411904, 0.010000769431557532, 0.0069430570515931905, 0.009327239068869739, 0.007309757585491762, 0.0072742121568766995, 0.008007020697638196, 0.006823823835212008, 0.005067252468975842, 0.009114061724249865, 0.00600948841098834, 0.006292285825857347, 0.006570149233191878, 0.009012011142623632, 0.004329706603047358, 0.00941465030913804, 0.006455904735702585, 0.006876947363237985, 0.005302443597632226, 0.004266359870354913, 0.009188217713141714, 0.0058110487749694975, 0.005980964920290714, 0.006129523260437089, 1.1239982138214444e-06], 'AVERAGE_MSE': 0.008670965446906395, 'timeTaken': '0:07:07.783616', 'modality':'eeg', 'cognitiveParent':'zuco_eeg'}
    word_error = np.array([['word', 'e1', 'e2', 'e3', 'e4', 'e5', 'e6', 'e7', 'e8', 'e9',
        'e10', 'e11', 'e12', 'e13', 'e14', 'e15', 'e16', 'e17', 'e18',
        'e19', 'e20', 'e21', 'e22', 'e23', 'e24', 'e25', 'e26', 'e27',
        'e28', 'e29', 'e30', 'e31', 'e32', 'e33', 'e34', 'e35', 'e36',
        'e37', 'e38', 'e39', 'e40', 'e41', 'e42', 'e43', 'e44', 'e45',
        'e46', 'e47', 'e48', 'e49', 'e50', 'e51', 'e52', 'e53', 'e54',
        'e55', 'e56', 'e57', 'e58', 'e59', 'e60', 'e61', 'e62', 'e63',
        'e64', 'e65', 'e66', 'e67', 'e68', 'e69', 'e70', 'e71', 'e72',
        'e73', 'e74', 'e75', 'e76', 'e77', 'e78', 'e79', 'e80', 'e81',
        'e82', 'e83', 'e84', 'e85', 'e86', 'e87', 'e88', 'e89', 'e90',
        'e91', 'e92', 'e93', 'e94', 'e95', 'e96', 'e97', 'e98', 'e99',
        'e100', 'e101', 'e102', 'e103', 'e104', 'e105'],
       ['penfield', '-0.12606644588215216', '-0.18044855579425936',
        '-0.17305442577353208', '-0.1656592269526594',
        '-0.04339210307171226', '0.0009934226102218946',
        '-0.19340365932976977', '-0.1278344690195083',
        '-0.1888622987190392', '-0.06879920522523003',
        '0.07608830311503678', '-0.17268547077031637',
        '-0.16387893300872075', '-0.0892056361511',
        '-0.028428396397623956', '0.01819335356978602',
        '-0.015049860678963523', '0.014521173622781602',
        '0.033107833411682774', '-0.02842350335939653',
        '0.06872538903910252', '-0.02730575260564161',
        '0.013951313314035874', '0.004852629470828207',
        '0.040069469385256795', '6.60427797793961e-05',
        '-0.01374769987158464', '0.05365396828078073',
        '0.03985177873459056', '0.012104275639210571',
        '-0.043859552476213204', '-0.032191721456163946',
        '0.05749127890783179', '-0.01049542758074995',
        '-0.011827139351250793', '-0.0031862676546215996',
        '-0.21037257241638951', '0.008538093952913384',
        '0.042926635162076954', '-0.024450902942870667',
        '0.019906679620287693', '-0.015565583101133207',
        '0.0224614466312133', '-0.04668596334894409',
        '0.01882814796990251', '0.02609046327378378',
        '-0.06253958186544284', '-0.0338896764544121',
        '-0.012134746657694873', '-0.05830857923916599',
        '0.02752094060217103', '0.07575472529545146',
        '-0.04980372217921469', '-0.07432777846783095',
        '0.0071495877736637015', '-0.0028065851575753697',
        '-0.026367279698328083', '-0.010098461650504653',
        '0.0123003994410259', '0.020306597715857966',
        '-0.02716092801576131', '-0.012035923985980135',
        '0.0016731523316250163', '0.048845954966987515',
        '-0.030085111495397443', '0.04508533422841088',
        '-0.02492962516923164', '-0.021169355744377838',
        '-0.02897377936804696', '0.0025329233293379105',
        '-0.024306675566554137', '-0.06378024519414593',
        '-0.05088890957131459', '-0.037517215593527276',
        '0.009230318323678322', '-0.0408879073717201',
        '-0.09391389129253219', '-0.15182825877988998',
        '0.003170006944770931', '-0.001726887987731407',
        '-0.08092208157154179', '-0.11935324770027173',
        '-0.02018266179921141', '-0.08508356944906659',
        '-0.030645520910325075', '-0.11934175793775295',
        '-0.139112345242644', '-0.11392126855494472',
        '-0.15496265416353378', '-0.12469066710259319',
        '-0.0754843044271798', '-0.13961999210916842',
        '-0.10734358533237132', '-0.17732782800746663',
        '0.0789867714648268', '-0.050424499758104147',
        '-0.1024508988931489', '-0.17811787188570827',
        '-0.22859924444361274', '0.07458373594957224',
        '0.1259390209352682', '-0.10225564374477963',
        '-0.21139195687489798', '-0.21997766324004459',
        '-0.0008214395493268967']], dtype='<U32')
    history = {'loss': np.array([0.25488953, 0.21478604, 0.17838786, 0.13976133, 0.1034061 ,
       0.07564405, 0.05683547, 0.04476263, 0.03682742, 0.03132567,
       0.02730239, 0.02424013, 0.02183606, 0.01990202, 0.01834059,
       0.01705953, 0.01599658, 0.01511453, 0.01438425, 0.01375044,
       0.01320592, 0.0127492 , 0.01233769, 0.01198298, 0.01166581,
       0.01139069, 0.01113193, 0.01091016, 0.01070138, 0.01051345,
       0.010342  , 0.01018741, 0.01004625, 0.00990824, 0.00978539,
       0.00967729, 0.00957047, 0.00947993, 0.00939412, 0.00931389,
       0.00923766, 0.00916925, 0.00910349, 0.00904588, 0.00899486,
       0.00894119, 0.0088909 , 0.0088536 , 0.00881352, 0.00876885,
       0.00873459, 0.00870241, 0.00867393, 0.00864445, 0.00861755,
       0.00859891, 0.00857205, 0.00855266, 0.00853562, 0.00851864,
       0.00850827, 0.00848854, 0.00847772, 0.00846338, 0.00845258,
       0.00843623, 0.00842589, 0.00841956, 0.00841243, 0.00840262,
       0.00839491, 0.0083887 , 0.00838005, 0.00837448, 0.0083664 ,
       0.00836016, 0.00835922, 0.00834551, 0.00834227, 0.00833735,
       0.0083334 , 0.00832747, 0.00832495, 0.00832293, 0.00831511,
       0.00830849, 0.00830687, 0.00830639, 0.00829938, 0.00829608,
       0.00829652, 0.00829227, 0.00829248, 0.00828477, 0.00828654,
       0.00828057, 0.00828322, 0.00827282, 0.00827123, 0.00827003]), 'val_loss': np.array([0.23047497, 0.19465619, 0.15752604, 0.11908325, 0.08707609,
       0.06454188, 0.04988362, 0.04041127, 0.03397305, 0.02937525,
       0.02590852, 0.02320042, 0.02105118, 0.01934954, 0.0179424 ,
       0.01681227, 0.01586363, 0.01507265, 0.01439631, 0.0138424 ,
       0.01334462, 0.01292574, 0.01254491, 0.01221056, 0.01193183,
       0.01166357, 0.01143143, 0.0112074 , 0.01101763, 0.01082873,
       0.01065693, 0.01050958, 0.01037207, 0.01023139, 0.01010608,
       0.00999653, 0.00988527, 0.00979189, 0.00969938, 0.00960981,
       0.00953708, 0.00945923, 0.00938345, 0.00931567, 0.0092655 ,
       0.00920798, 0.00915692, 0.00910952, 0.00905618, 0.00901505,
       0.00898051, 0.00894775, 0.00891546, 0.0088867 , 0.00885898,
       0.00883877, 0.00881933, 0.00879048, 0.00877203, 0.00876519,
       0.00873774, 0.00872758, 0.00871757, 0.00869121, 0.00868277,
       0.00866514, 0.008663  , 0.00864658, 0.00863893, 0.00862224,
       0.00861719, 0.00861065, 0.00859434, 0.0085942 , 0.00859378,
       0.0085781 , 0.00857631, 0.0085627 , 0.00855698, 0.00855979,
       0.00855273, 0.00854975, 0.00853534, 0.00854033, 0.00853054,
       0.0085231 , 0.00852784, 0.0085172 , 0.00851355, 0.00851821,
       0.00851931, 0.00851091, 0.00850721, 0.00850302, 0.00850081,
       0.00850148, 0.00850097, 0.00849433, 0.00848764, 0.00849617])}
    return logging, word_error, history

@pytest.fixture
def all_runs():
    return {17.0: {'cognitiveData': 'zuco-eeg', 'feature': 'ALL_DIM', 'wordEmbedding': 'glove-50', 'AVERAGE_MSE': 0.008630327568270158}}


def test_update_run_id(tmpdir, config):
    path = tmpdir / 'output' / 'config.json'
    update_run_id(path)
    with open(path, 'r') as f:
        config = json.load(f)
    assert config['run_id'] == 2


def test_write_results(tmpdir, config, results):
    shutil.rmtree(tmpdir / 'output')
    logging, word_error, history = results
    write_results(config, logging, word_error, history)
    refdir = Path('tests/reference/test_writeResults_results')
    # Fix missing newline
    with open(tmpdir / 'mapping_1.json', 'r') as f_in:
        f_str = f_in.read()
        with open(tmpdir / 'mapping_1.json', 'w') as f_out:
            f_out.write(f_str + '\n')
    assert not filecmp.dircmp(refdir, tmpdir).diff_files


def test_write_options(config, all_runs, tmpdir):
    outputDir = tmpdir/ "experiments" / 'eeg'
    if not os.path.exists(outputDir):
        os.makedirs(outputDir)
    write_options(config, 'eeg', all_runs)
    with open(outputDir / 'options_1.json') as f:
        options_str = f.read()
    ref_str = """{
    "17.0": {
        "AVERAGE_MSE": 0.008630327568270158,
        "cognitiveData": "zuco-eeg",
        "feature": "ALL_DIM",
        "wordEmbedding": "glove-50"
    }
}"""
    assert options_str == ref_str
