import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class ExtractEven{
  public static ArrayList<Object> extractEven(List<Object> testTuple){
    ArrayList<Object> list = new ArrayList<>();
    for (int i = 0; i < testTuple.size(); i++){
      if (testTuple.get(i) instanceof List){
        list.add(extractEven((List<Object>) testTuple.get(i)));
      } else {
        if (testTuple.get(i) instanceof int){
          if (((int) testTuple.get(i)) % 2 == 0){
            list.add(testTuple.get(i));
          }
        } else {
          list.add(testTuple.get(i));
        }
      }
    }
    return list;
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
        List<Object> arg00 = Arrays.asList(4, 5, Arrays.asList(7, 6, Arrays.asList(2, 4)), 6, 8);
        List<Object> x0 = ExtractEven.extractEven(Arrays.asList(4, 5, Arrays.asList(7, 6, Arrays.asList(2, 4)), 6, 8));
        List<Object> v0 = Arrays.asList(4, Arrays.asList(6, Arrays.asList(2, 4)), 6, 8);
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<Object> arg10 = Arrays.asList(5, 6, Arrays.asList(8, 7, Arrays.asList(4, 8)), 7, 9);
        List<Object> x1 = ExtractEven.extractEven(Arrays.asList(5, 6, Arrays.asList(8, 7, Arrays.asList(4, 8)), 7, 9));
        List<Object> v1 = Arrays.asList(6, Arrays.asList(8, Arrays.asList(4, 8)));
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<Object> arg20 = Arrays.asList(5, 6, Arrays.asList(9, 8, Arrays.asList(4, 6)), 8, 10);
        List<Object> x2 = ExtractEven.extractEven(Arrays.asList(5, 6, Arrays.asList(9, 8, Arrays.asList(4, 6)), 8, 10));
        List<Object> v2 = Arrays.asList(6, Arrays.asList(8, Arrays.asList(4, 6)), 8, 10);
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
