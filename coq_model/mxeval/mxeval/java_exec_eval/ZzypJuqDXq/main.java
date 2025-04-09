import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class ExtractFreq{
  public static Integer extractFreq(List<List<Integer>> testList){
    ArrayList<Integer> freqList = new ArrayList<>();
    for (int i = 0; i < testList.size(); i++){
      freqList.add(0);
    }
    for (int i = 0; i < testList.size(); i++){
      for (int j = 0; j < testList.get(i).size(); j++){
        freqList.set(i, freqList.get(i) + testList.get(i).get(j));
      }
    }
    HashSet<Integer> set = new HashSet<Integer>();
    for (int freq : freqList){
      set.add(freq);
    }
    return set.size();
  }
}

class Main {
    public static boolean compare(Object obj1, Object obj2) {
        if (obj1 == null && obj2 == null){
            return true;
        } else if (obj1 == null || obj2 == null){
            return false;
        } else {
            return obj1.equals(obj2);
        }
    }
    
    public static void main(String[] args) throws Exception {
        List<List<Integer>> arg00 = Arrays.asList(Arrays.asList(3, 4), Arrays.asList(1, 2), Arrays.asList(4, 3), Arrays.asList(5, 6));
        int x0 = ExtractFreq.extractFreq(Arrays.asList(Arrays.asList(3, 4), Arrays.asList(1, 2), Arrays.asList(4, 3), Arrays.asList(5, 6)));
        int v0 = 3;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<List<Integer>> arg10 = Arrays.asList(Arrays.asList(4, 15), Arrays.asList(2, 3), Arrays.asList(5, 4), Arrays.asList(6, 7));
        int x1 = ExtractFreq.extractFreq(Arrays.asList(Arrays.asList(4, 15), Arrays.asList(2, 3), Arrays.asList(5, 4), Arrays.asList(6, 7)));
        int v1 = 4;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<List<Integer>> arg20 = Arrays.asList(Arrays.asList(5, 16), Arrays.asList(2, 3), Arrays.asList(6, 5), Arrays.asList(6, 9));
        int x2 = ExtractFreq.extractFreq(Arrays.asList(Arrays.asList(5, 16), Arrays.asList(2, 3), Arrays.asList(6, 5), Arrays.asList(6, 9)));
        int v2 = 4;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
